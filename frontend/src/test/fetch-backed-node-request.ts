import { EventEmitter } from "node:events";
import type { ClientRequest, IncomingMessage, RequestOptions } from "node:http";
import { Readable } from "node:stream";

type ResponseHandler = (response: IncomingMessage) => void;

/**
 * Adapt mocked Node HTTP requests to the test's stubbed global fetch.
 *
 * Production uses node:http(s) directly so DNS pinning controls the socket.
 * Route tests keep their concise fetch fixtures by installing this adapter as
 * the mocked node:https request implementation.
 */
export function createFetchBackedNodeRequest() {
  return (
    options: RequestOptions,
    handleResponse: ResponseHandler,
  ): ClientRequest => {
    const headers = new Headers(options.headers as HeadersInit);
    const authority =
      headers.get("host") ??
      `${String(options.hostname ?? "")}${
        options.port ? `:${String(options.port)}` : ""
      }`;
    const target = new URL(
      `${String(options.protocol ?? "http:")}//${authority}${String(
        options.path ?? "/",
      )}`,
    );
    const events = new EventEmitter();
    const request = events as unknown as ClientRequest;
    let destroyed = false;

    request.destroy = ((error?: Error) => {
      destroyed = true;
      if (error) events.emit("error", error);
      return request;
    }) as ClientRequest["destroy"];

    request.end = ((body?: string | Uint8Array) => {
      if (destroyed) return request;
      void Promise.resolve()
        .then(() =>
          globalThis.fetch(target, {
            body: body as BodyInit | undefined,
            headers,
            method: options.method,
            signal: options.signal,
          }),
        )
        .then(async (response) => {
          if (destroyed) return;
          const bytes = new Uint8Array(await response.arrayBuffer());
          const incoming = Readable.from(
            bytes.byteLength > 0 ? [bytes] : [],
          ) as IncomingMessage;
          incoming.rawHeaders = Array.from(response.headers.entries()).flat();
          incoming.statusCode = response.status;
          incoming.statusMessage = response.statusText;
          handleResponse(incoming);
        })
        .catch((error: unknown) => {
          events.emit(
            "error",
            error instanceof Error ? error : new Error(String(error)),
          );
        });
      return request;
    }) as ClientRequest["end"];

    return request;
  };
}
