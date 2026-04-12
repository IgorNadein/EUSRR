"use client";

import Link from "next/link";

export function AuthLegalNotice({
  prefix = "Продолжая, вы соглашаетесь с ",
}: {
  prefix?: string;
}) {
  return (
    <p className="app-text-muted mt-6 text-center text-xs leading-5">
      {prefix}
      <Link href="/legal/terms" className="app-link-accent font-medium">
        условиями использования
      </Link>{" "}
      и подтверждаете ознакомление с{" "}
      <Link href="/legal/privacy" className="app-link-accent font-medium">
        политикой конфиденциальности
      </Link>
      .
    </p>
  );
}
