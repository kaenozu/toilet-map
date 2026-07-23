import type { ReactNode } from "react";

export const metadata = {
  title: "トイレきれい度マップ v2",
  description: "公開トイレのきれい度を地図と一覧で確認",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
