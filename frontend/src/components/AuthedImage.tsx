import React, { useEffect, useState } from "react";

/**
 * An `<img>` for a backend route that requires the bearer token.
 *
 * Screenshot bytes are proxied by `/time-entry-screenshots/{id}/view`, which is
 * authorised per request — a plain `<img src>` sends no `Authorization` header,
 * so the browser would render a broken tile for every capture. The bytes are
 * fetched here instead and handed to the tag as an object URL, which is revoked
 * when the tile unmounts so a long scroll does not leak one blob per image.
 *
 * A failed load renders an honest "image unavailable" panel rather than a
 * placeholder picture: the record exists, the image could not be read, and the
 * viewer should be able to tell those apart.
 */
export const AuthedImage: React.FC<{
  url: string;
  alt: string;
  className?: string;
  /** Rendered in place of the image while loading and on failure. */
  frameClassName?: string;
}> = ({ url, alt, className = "", frameClassName = "" }) => {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let revoked = false;
    let created: string | null = null;
    setObjectUrl(null);
    setFailed(false);

    const token = localStorage.getItem("accessToken");
    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.blob();
      })
      .then((blob) => {
        if (revoked) return;
        created = URL.createObjectURL(blob);
        setObjectUrl(created);
      })
      .catch(() => {
        if (!revoked) setFailed(true);
      });

    return () => {
      revoked = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [url]);

  if (failed) {
    return (
      <div
        className={`flex items-center justify-center bg-[#F1F5F9] px-3 text-center ${frameClassName}`}
      >
        <span className="text-[10px] font-semibold text-[#94A3B8]">Image unavailable</span>
      </div>
    );
  }

  if (!objectUrl) {
    return <div className={`animate-pulse bg-[#E2E8F0] ${frameClassName}`} />;
  }

  return <img src={objectUrl} alt={alt} loading="lazy" className={className} />;
};
