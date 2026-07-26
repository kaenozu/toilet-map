// Root layout and metadata for public and administrator interfaces.
import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "トイレきれい度マップ",
  description: "清潔度、設備、情報の新しさと信頼度から公共トイレを検索",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body><a href="#main" className="skip-link">メインコンテンツへスキップ</a>{children}</body>
    </html>
  );
}
