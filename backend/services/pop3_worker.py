import asyncio
from dataclasses import dataclass
import datetime
import logging
import poplib
from typing import Literal, Mapping

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import TenantConfig
from db.pop3_collection_models import Pop3ObservedMessage
from db.session import AsyncSessionLocal
from services.email_client import validate_pop3_destination
from services.email_parser import parse_eml_bytes
from services.exceptions import EmailParseError
from services.imap_worker import persist_fetched_email

logger = logging.getLogger(__name__)
MAX_POP3_FETCH_MESSAGES = 10
POP3_RETRY_DELAY = datetime.timedelta(seconds=60)
Pop3CollectionDisposition = Literal["observed", "retryable"]


@dataclass(frozen=True)
class Pop3MessageIdentity:
    """Current-session POP3 number bound to its RFC 1939 durable unique-id."""

    message_number: int
    provider_uidl: str


@dataclass(frozen=True)
class Pop3RetrievedMessage:
    """Retrieved POP3 source bytes plus optional provider progress identity."""

    source_content: bytes
    provider_uidl: str | None = None


@dataclass(frozen=True)
class Pop3CollectionProgressState:
    """Durable collection disposition for one owner-scoped provider UIDL."""

    disposition: Pop3CollectionDisposition
    retry_after: datetime.datetime | None


@dataclass(frozen=True)
class Pop3SyncBatch:
    """Network retrieval result plus retryable UIDLs awaiting durable disposition."""

    messages: list[Pop3RetrievedMessage]
    retryable_uidls: frozenset[str]


class Pop3SyncWorker:
    def __init__(self):
        self._task = None
        self._is_running = False

    async def start(self):
        if self._is_running:
            logger.warning("Pop3SyncWorker is already running.")
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Pop3SyncWorker started.")

    async def stop(self):
        if not self._is_running:
            return
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Pop3SyncWorker stopped.")

    async def _run_loop(self):
        while self._is_running:
            try:
                await self._sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Pop3SyncWorker loop: {e}", exc_info=True)
            if self._is_running:
                try:
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    break

    async def _sync(self):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TenantConfig).where(TenantConfig.pop3_server.isnot(None))
            )
            configs = result.scalars().all()

        semaphore = asyncio.Semaphore(10)
        tasks = []
        for config in configs:
            if not config.pop3_server or not config.pop3_port:
                continue
            tasks.append(self._sync_tenant(config, semaphore))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _sync_tenant(self, config: TenantConfig, semaphore: asyncio.Semaphore):
        async with semaphore:
            try:
                pop3_server, pop3_port = self._validated_destination(config)
            except ValueError:
                logger.info(
                    "Skipping POP3 sync for user %s due to mail destination policy",
                    config.user_id,
                )
                return
            logger.info(
                f"Connecting to POP3 server {pop3_server}:{pop3_port} for user {config.user_id}"
            )
            try:
                collection_progress = await self._load_collection_progress(config)
                batch = await asyncio.to_thread(
                    self._do_pop3_sync_batch,
                    config,
                    pop3_server,
                    pop3_port,
                    collection_progress,
                )
                imported_count = await self._import_messages(
                    config,
                    batch.messages,
                    retryable_uidls=batch.retryable_uidls,
                )
                logger.info(
                    "Successfully synced POP3 server for user %s with %s imported messages.",
                    config.user_id,
                    imported_count,
                )
            except Exception as e:
                logger.error(
                    "Failed to connect or sync with POP3 server for user %s: %s",
                    config.user_id,
                    type(e).__name__,
                )

    async def _load_collection_progress(
        self, config: TenantConfig
    ) -> dict[str, Pop3CollectionProgressState]:
        """Load durable UIDL collection state before provider network I/O begins."""
        if config.id is None:
            return {}
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(
                    Pop3ObservedMessage.provider_uidl,
                    Pop3ObservedMessage.collection_disposition,
                    Pop3ObservedMessage.retry_after,
                ).where(Pop3ObservedMessage.tenant_config_id == config.id)
            )
            return {
                provider_uidl: Pop3CollectionProgressState(
                    disposition=disposition,
                    retry_after=retry_after,
                )
                for provider_uidl, disposition, retry_after in result.all()
            }

    async def _load_observed_uidls(self, config: TenantConfig) -> set[str]:
        """Compatibility view over durable collection state for observed UIDLs."""
        progress = await self._load_collection_progress(config)
        return {
            provider_uidl
            for provider_uidl, state in progress.items()
            if state.disposition == "observed"
        }

    async def _import_messages(
        self,
        config: TenantConfig,
        messages: list[Pop3RetrievedMessage | bytes],
        *,
        retryable_uidls: frozenset[str] | set[str] | None = None,
    ) -> int:
        retryable_uidls = retryable_uidls or frozenset()
        if not messages and not retryable_uidls:
            return 0

        imported_count = 0
        owner_addresses = [config.pop3_username] if config.pop3_username else None
        state_time = datetime.datetime.now(datetime.timezone.utc)
        async with AsyncSessionLocal() as session:
            try:
                if config.id is not None:
                    for provider_uidl in retryable_uidls:
                        await self._upsert_collection_progress(
                            session,
                            config.id,
                            provider_uidl,
                            disposition="retryable",
                            state_time=state_time,
                        )
                for message in messages:
                    if isinstance(message, bytes):
                        raw_message = message
                        provider_uidl = None
                    else:
                        raw_message = message.source_content
                        provider_uidl = message.provider_uidl
                    try:
                        email_data = parse_eml_bytes(raw_message)
                    except EmailParseError:
                        logger.info(
                            "Skipping unparsable POP3 message for user %s.",
                            config.user_id,
                        )
                        if provider_uidl is not None and config.id is not None:
                            await self._upsert_collection_progress(
                                session,
                                config.id,
                                provider_uidl,
                                disposition="retryable",
                                state_time=state_time,
                            )
                        continue
                    persistence_result = await persist_fetched_email(
                        session,
                        email_data,
                        config.user_id,
                        config.organization_id,
                        owner_addresses=owner_addresses,
                        source_content=raw_message,
                    )
                    if persistence_result.created_record:
                        imported_count += 1
                    if provider_uidl is not None and config.id is not None:
                        await self._upsert_collection_progress(
                            session,
                            config.id,
                            provider_uidl,
                            disposition="observed",
                            state_time=state_time,
                        )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return imported_count

    async def _upsert_collection_progress(
        self,
        session,
        tenant_config_id: int,
        provider_uidl: str,
        *,
        disposition: Pop3CollectionDisposition,
        state_time: datetime.datetime,
    ) -> None:
        retry_after = (
            state_time + POP3_RETRY_DELAY if disposition == "retryable" else None
        )
        observed_at = state_time if disposition == "observed" else None
        statement = (
            pg_insert(Pop3ObservedMessage)
            .values(
                tenant_config_id=tenant_config_id,
                provider_uidl=provider_uidl,
                collection_disposition=disposition,
                retry_after=retry_after,
                observed_at=observed_at,
            )
            .on_conflict_do_update(
                index_elements=["tenant_config_id", "provider_uidl"],
                set_={
                    "collection_disposition": disposition,
                    "retry_after": retry_after,
                    "observed_at": observed_at,
                },
            )
        )
        await session.execute(statement)

    def _validated_destination(self, config: TenantConfig) -> tuple[str, int]:
        return validate_pop3_destination(
            str(config.pop3_server),
            int(config.pop3_port),  # type: ignore[arg-type]
        )

    def _do_pop3_sync(
        self,
        config: TenantConfig,
        pop3_server: str | None = None,
        pop3_port: int | None = None,
        observed_uidls: set[str] | None = None,
    ) -> list[Pop3RetrievedMessage]:
        collection_progress = {
            provider_uidl: Pop3CollectionProgressState(
                disposition="observed",
                retry_after=None,
            )
            for provider_uidl in (observed_uidls or set())
        }
        return self._do_pop3_sync_batch(
            config,
            pop3_server,
            pop3_port,
            collection_progress,
        ).messages

    def _do_pop3_sync_batch(
        self,
        config: TenantConfig,
        pop3_server: str | None = None,
        pop3_port: int | None = None,
        collection_progress: Mapping[str, Pop3CollectionProgressState] | None = None,
    ) -> Pop3SyncBatch:
        if pop3_server is None or pop3_port is None:
            pop3_server, pop3_port = self._validated_destination(config)
        pop3_client = poplib.POP3_SSL(pop3_server, pop3_port)
        collection_progress = collection_progress or {}
        try:
            if not config.pop3_username:
                logger.error(
                    "POP3 account configuration incomplete for user %s.",
                    config.user_id,
                )
                raise RuntimeError(
                    f"POP3 account configuration incomplete for user {config.user_id}"
                )
            if not config.pop3_password:
                logger.error(
                    "POP3 account configuration incomplete for user %s.",
                    config.user_id,
                )
                raise RuntimeError(
                    f"POP3 account configuration incomplete for user {config.user_id}"
                )
            pop3_client.user(config.pop3_username)
            pop3_client.pass_(config.pop3_password)

            uidl_identities = self._current_uidl_identities(pop3_client, config)
            if uidl_identities is not None:
                selected = self._select_uidl_candidates(
                    uidl_identities,
                    collection_progress,
                    datetime.datetime.now(datetime.timezone.utc),
                )
                return self._retrieve_uidl_batch(pop3_client, config, selected)

            _response, listings, _octets = pop3_client.list()
            message_numbers = [
                message_number
                for listing in listings
                if (message_number := self._message_number_from_listing(listing))
                is not None
            ]
            logger.warning(
                "POP3 UIDL unavailable for user %s; bounded fallback cannot prove durable backlog progress.",
                config.user_id,
            )
            return Pop3SyncBatch(
                messages=self._retrieve_fallback_messages(
                    pop3_client,
                    config,
                    sorted(message_numbers)[-MAX_POP3_FETCH_MESSAGES:],
                ),
                retryable_uidls=frozenset(),
            )
        finally:
            self._close_pop3_client(pop3_client, config)

    def _select_uidl_candidates(
        self,
        identities: list[Pop3MessageIdentity],
        collection_progress: Mapping[str, Pop3CollectionProgressState],
        now: datetime.datetime,
    ) -> list[Pop3MessageIdentity]:
        """Prefer never-attempted UIDLs, then retries whose retry window is due."""
        fresh: list[Pop3MessageIdentity] = []
        due_retries: list[Pop3MessageIdentity] = []
        for identity in sorted(
            identities,
            key=lambda candidate: candidate.message_number,
            reverse=True,
        ):
            state = collection_progress.get(identity.provider_uidl)
            if state is None:
                fresh.append(identity)
                continue
            if state.disposition == "observed":
                continue
            if state.retry_after is None or state.retry_after <= now:
                due_retries.append(identity)
        return (fresh + due_retries)[:MAX_POP3_FETCH_MESSAGES]

    def _current_uidl_identities(
        self,
        pop3_client: poplib.POP3_SSL,
        config: TenantConfig,
    ) -> list[Pop3MessageIdentity] | None:
        try:
            _response, listings, _octets = pop3_client.uidl()
        except poplib.error_proto:
            return None

        identities: list[Pop3MessageIdentity] = []
        for listing in listings:
            identity = self._uidl_identity_from_listing(listing)
            if identity is None:
                logger.warning(
                    "POP3 UIDL response contained an invalid entry for user %s; durable progress is unavailable for this poll.",
                    config.user_id,
                )
                return None
            identities.append(identity)
        return identities

    def _uidl_identity_from_listing(
        self, listing: bytes | str
    ) -> Pop3MessageIdentity | None:
        try:
            raw_listing = listing.decode("ascii") if isinstance(listing, bytes) else listing
        except UnicodeDecodeError:
            return None
        parts = raw_listing.strip().split()
        if len(parts) != 2 or not parts[0].isdigit():
            return None
        provider_uidl = parts[1]
        if not 1 <= len(provider_uidl) <= 70:
            return None
        if any(not 0x21 <= ord(character) <= 0x7E for character in provider_uidl):
            return None
        return Pop3MessageIdentity(
            message_number=int(parts[0]),
            provider_uidl=provider_uidl,
        )

    def _retrieve_uidl_batch(
        self,
        pop3_client: poplib.POP3_SSL,
        config: TenantConfig,
        identities: list[Pop3MessageIdentity],
    ) -> Pop3SyncBatch:
        messages: list[Pop3RetrievedMessage] = []
        retryable_uidls: set[str] = set()
        for identity in identities:
            try:
                source_content = self._retrieve_message(
                    pop3_client, identity.message_number
                )
            except poplib.error_proto as exc:
                if not self._is_negative_pop3_response(exc):
                    logger.warning(
                        "POP3 RETR stopped after malformed protocol response for user %s: %s",
                        config.user_id,
                        type(exc).__name__,
                    )
                    break
                logger.warning(
                    "POP3 RETR rejected one message for user %s; continuing bounded batch: %s",
                    config.user_id,
                    type(exc).__name__,
                )
                retryable_uidls.add(identity.provider_uidl)
                continue
            except OSError as exc:
                logger.warning(
                    "POP3 RETR stopped after transport failure for user %s: %s",
                    config.user_id,
                    type(exc).__name__,
                )
                break
            messages.append(
                Pop3RetrievedMessage(
                    source_content=source_content,
                    provider_uidl=identity.provider_uidl,
                )
            )
        return Pop3SyncBatch(
            messages=messages,
            retryable_uidls=frozenset(retryable_uidls),
        )

    def _retrieve_uidl_messages(
        self,
        pop3_client: poplib.POP3_SSL,
        config: TenantConfig,
        identities: list[Pop3MessageIdentity],
    ) -> list[Pop3RetrievedMessage]:
        """Compatibility wrapper retaining the historical direct-return contract."""
        return self._retrieve_uidl_batch(pop3_client, config, identities).messages

    def _retrieve_fallback_messages(
        self,
        pop3_client: poplib.POP3_SSL,
        config: TenantConfig,
        message_numbers: list[int],
    ) -> list[Pop3RetrievedMessage]:
        messages: list[Pop3RetrievedMessage] = []
        for message_number in message_numbers:
            try:
                source_content = self._retrieve_message(pop3_client, message_number)
            except poplib.error_proto as exc:
                if not self._is_negative_pop3_response(exc):
                    logger.warning(
                        "POP3 fallback RETR stopped after malformed protocol response for user %s: %s",
                        config.user_id,
                        type(exc).__name__,
                    )
                    break
                logger.warning(
                    "POP3 fallback RETR rejected one message for user %s; continuing bounded batch: %s",
                    config.user_id,
                    type(exc).__name__,
                )
                continue
            except OSError as exc:
                logger.warning(
                    "POP3 fallback RETR stopped after transport failure for user %s: %s",
                    config.user_id,
                    type(exc).__name__,
                )
                break
            messages.append(
                Pop3RetrievedMessage(
                    source_content=source_content,
                    provider_uidl=None,
                )
            )
        return messages

    def _retrieve_message(self, pop3_client: poplib.POP3_SSL, message_number: int) -> bytes:
        _retr_response, lines, _retr_octets = pop3_client.retr(message_number)
        return self._message_bytes(lines)

    def _is_negative_pop3_response(self, error: poplib.error_proto) -> bool:
        """Return whether a protocol exception carries an RFC 1939 -ERR reply."""
        if not error.args:
            return False
        response = error.args[0]
        if isinstance(response, bytes):
            return response.startswith(b"-ERR")
        return str(response).startswith("-ERR")

    def _close_pop3_client(
        self,
        pop3_client: poplib.POP3_SSL,
        config: TenantConfig,
    ) -> None:
        try:
            pop3_client.quit()
        except (OSError, poplib.error_proto) as exc:
            logger.warning(
                "POP3 QUIT cleanup failed for user %s: %s",
                config.user_id,
                type(exc).__name__,
            )
            try:
                pop3_client.close()
            except OSError as close_exc:
                logger.warning(
                    "POP3 transport close failed for user %s: %s",
                    config.user_id,
                    type(close_exc).__name__,
                )

    def _message_bytes(self, lines: list[bytes | str]) -> bytes:
        """Reconstruct one POP3 RETR message with protocol CRLF terminators."""
        return b"\r\n".join(self._bytes_line(line) for line in lines) + b"\r\n"

    def _message_number_from_listing(self, listing: bytes | str) -> int | None:
        raw_listing = (
            listing.decode("ascii", errors="ignore")
            if isinstance(listing, bytes)
            else listing
        )
        candidate = (
            raw_listing.strip().split(maxsplit=1)[0] if raw_listing.strip() else ""
        )
        if not candidate.isdigit():
            return None
        return int(candidate)

    def _bytes_line(self, line: bytes | str) -> bytes:
        return (
            line if isinstance(line, bytes) else line.encode("utf-8", errors="replace")
        )
