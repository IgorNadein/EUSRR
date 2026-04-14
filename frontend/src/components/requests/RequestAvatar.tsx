import Image from "next/image";
import { resolveMediaUrl } from "@/lib/url";

const avatarSizeMap = {
  sm: { className: "h-6 w-6 text-[11px]", px: 24 },
  md: { className: "h-7 w-7 text-xs", px: 28 },
  lg: { className: "h-8 w-8 text-xs", px: 32 },
} as const;

type RequestAvatarProps = {
  alt: string;
  fallback: string;
  size?: keyof typeof avatarSizeMap;
  src?: string | null;
};

export function RequestAvatar({
  alt,
  fallback,
  size = "md",
  src,
}: RequestAvatarProps) {
  const config = avatarSizeMap[size];
  const resolvedSrc = resolveMediaUrl(src);

  if (resolvedSrc) {
    return (
      <span className={`app-avatar-frame relative shrink-0 overflow-hidden rounded-full ${config.className}`}>
        <Image
          src={resolvedSrc}
          alt={alt}
          width={config.px}
          height={config.px}
          unoptimized
          className="h-full w-full object-cover"
        />
      </span>
    );
  }

  return (
    <span
      className={`app-avatar-fallback flex shrink-0 items-center justify-center rounded-full font-semibold ${config.className}`}
    >
      {fallback}
    </span>
  );
}
