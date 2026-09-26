import { WorkspaceHome } from '@/components/WorkspaceHome';
import type { MailFolder } from '@/components/EmailList';

type MailPageProps = {
  searchParams?: Promise<{
    folder?: string | string[];
    id?: string | string[];
  }>;
};

function normalizeMailFolder(value: string | string[] | undefined): MailFolder {
  const rawValue = Array.isArray(value) ? value[0] : value;
  return rawValue === 'sent' ? 'sent' : 'inbox';
}

function normalizeMailId(value: string | string[] | undefined): number | null {
  if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value)) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) ? id : null;
}

export default async function MailPage({ searchParams }: MailPageProps) {
  const params = searchParams ? await searchParams : {};
  const initialEmailId = normalizeMailId(params.id);
  return <WorkspaceHome key={initialEmailId ?? 'inbox'} forcedStartupView="email" mailFolder={normalizeMailFolder(params.folder)} initialEmailId={initialEmailId} />;
}
