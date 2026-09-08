/**
 * The Monitra desktop download page.
 *
 * The one thing this page must get right: **it never links to a versioned
 * file.** Every button points at the backend's "latest published release" for
 * a platform, so a release published a year from now is served without this
 * file being edited. That is the entire reason the page fetches instead of
 * hardcoding.
 *
 * Public and unauthenticated: a new member installing Monitra for the first
 * time has no account yet, and asking them to sign in before they can download
 * the thing they sign in with is a loop.
 *
 * Honest empty states. When a deployment has published nothing for a platform,
 * the card says so and offers no link. A dead download button is worse than an
 * absent one, and inventing a URL here would be exactly the fabricated-data
 * pattern this project has already removed once.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  detectDownloadKey,
  downloadUrlFor,
  fetchDesktopDownloadsAPI,
  formatFileSize,
} from '../../api/desktopRelease';
import type { DesktopDownloadIndex, DesktopRelease, DownloadKey } from '../../api/desktopRelease';

/** Display order and copy for each build. */
const CARDS: Array<{
  key: DownloadKey;
  title: string;
  subtitle: string;
  note?: string;
}> = [
  {
    key: 'windows',
    title: 'Windows',
    subtitle: 'Windows 10 and 11, 64-bit',
    note: 'Installs without administrator rights.',
  },
  {
    key: 'macos-arm64',
    title: 'macOS — Apple Silicon',
    subtitle: 'M1, M2, M3 and later',
  },
  {
    key: 'macos-x86_64',
    title: 'macOS — Intel',
    subtitle: 'Intel-based Macs',
  },
];

const WindowsIcon = () => (
  <svg className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M3 5.5 10.2 4.5v7.1H3V5.5Zm0 13 7.2 1v-7H3v6ZM11.4 4.3 21 3v8.6h-9.6V4.3Zm0 8.5H21V21l-9.6-1.3v-6.9Z" />
  </svg>
);

const AppleIcon = () => (
  <svg className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M16.4 12.8c0-2.3 1.9-3.4 2-3.5-1.1-1.6-2.8-1.8-3.4-1.8-1.4-.1-2.8.9-3.5.9-.7 0-1.9-.9-3-.8-1.6 0-3 .9-3.8 2.3-1.6 2.8-.4 7 1.2 9.3.8 1.1 1.7 2.4 2.9 2.3 1.2 0 1.6-.7 3-.7s1.8.7 3 .7c1.2 0 2-1.1 2.8-2.2.9-1.3 1.2-2.5 1.3-2.6-.1 0-2.5-1-2.5-3.9ZM14.2 5.9c.6-.8 1-1.9.9-3-.9 0-2 .6-2.7 1.4-.6.7-1.1 1.8-.9 2.9 1 .1 2-.5 2.7-1.3Z" />
  </svg>
);

function CardIcon({ platformKey }: { platformKey: DownloadKey }) {
  return platformKey === 'windows' ? <WindowsIcon /> : <AppleIcon />;
}

function DownloadCard({
  card,
  release,
  recommended,
}: {
  card: (typeof CARDS)[number];
  release: DesktopRelease | undefined;
  recommended: boolean;
}) {
  const available = Boolean(release?.available);
  const size = formatFileSize(release?.file_size ?? null);

  return (
    <div
      className={`relative flex flex-col rounded-xl border bg-white p-6 shadow-sm transition ${
        recommended ? 'border-indigo-400 ring-1 ring-indigo-200' : 'border-slate-200'
      }`}
    >
      {recommended && (
        <span className="absolute -top-3 left-6 rounded-full bg-indigo-600 px-3 py-1 text-xs font-semibold text-white">
          Recommended for your device
        </span>
      )}

      <div className="flex items-center gap-3 text-slate-800">
        <CardIcon platformKey={card.key} />
        <div>
          <h3 className="text-base font-semibold text-slate-900">{card.title}</h3>
          <p className="text-sm text-slate-500">{card.subtitle}</p>
        </div>
      </div>

      <dl className="mt-5 space-y-1 text-sm">
        <div className="flex justify-between">
          <dt className="text-slate-500">Version</dt>
          <dd className="font-medium text-slate-900">
            {available ? release?.version : '—'}
          </dd>
        </div>
        {size && (
          <div className="flex justify-between">
            <dt className="text-slate-500">Size</dt>
            <dd className="font-medium text-slate-900">{size}</dd>
          </div>
        )}
      </dl>

      {card.note && <p className="mt-3 text-xs text-slate-500">{card.note}</p>}

      {available ? (
        <a
          href={downloadUrlFor(card.key)}
          className="mt-5 inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700"
        >
          Download for {card.title.split('—')[0].trim()}
        </a>
      ) : (
        /* No published build for this platform. Said plainly, with no link:
           a button that 404s is worse than no button. */
        <span className="mt-5 inline-flex cursor-not-allowed items-center justify-center rounded-lg bg-slate-100 px-4 py-2.5 text-sm font-medium text-slate-400">
          Not available yet
        </span>
      )}

      {available && release?.sha256 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700">
            Verify this download
          </summary>
          <p className="mt-2 text-xs text-slate-500">
            SHA-256 checksum. Compare it against the file you downloaded with{' '}
            <code className="rounded bg-slate-100 px-1">
              {card.key === 'windows' ? 'Get-FileHash <file>' : 'shasum -a 256 <file>'}
            </code>
            .
          </p>
          <code className="mt-2 block break-all rounded bg-slate-50 p-2 text-[11px] text-slate-600">
            {release.sha256}
          </code>
        </details>
      )}
    </div>
  );
}

export function DownloadPage() {
  const [index, setIndex] = useState<DesktopDownloadIndex | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const recommended = useMemo(() => detectDownloadKey(), []);

  useEffect(() => {
    let cancelled = false;
    fetchDesktopDownloadsAPI()
      .then((result) => {
        if (!cancelled) setIndex(result);
      })
      .catch((err: Error) => {
        // A failed request is reported as a failure, not rendered as "nothing
        // is available" — those are different facts and the user can act on
        // one of them.
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 py-16">
      <div className="mx-auto max-w-5xl px-6">
        <header className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Download Monitra Desktop
          </h1>
          <p className="mt-3 text-slate-600">
            Install Monitra once. It keeps itself up to date from then on — you
            will be told when a new version is ready and can install it without
            coming back here.
          </p>
          {index?.latest_version && (
            <p className="mt-2 text-sm text-slate-500">
              Latest version: <span className="font-semibold">{index.latest_version}</span>
            </p>
          )}
        </header>

        {loading && (
          <p className="mt-12 text-center text-sm text-slate-500">
            Loading the latest release…
          </p>
        )}

        {error && !loading && (
          <div className="mt-12 rounded-lg border border-amber-200 bg-amber-50 p-4 text-center text-sm text-amber-800">
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {CARDS.map((card) => (
                <DownloadCard
                  key={card.key}
                  card={card}
                  release={index?.downloads?.[card.key]}
                  recommended={recommended === card.key}
                />
              ))}
            </div>

            <p className="mt-8 text-center text-xs text-slate-500">
              macOS ships one build per processor. Apple Silicon and Intel are
              different downloads — if you are unsure, choose Apple Silicon for
              any Mac bought in 2020 or later.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default DownloadPage;
