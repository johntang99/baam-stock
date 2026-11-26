import type { ReactNode } from "react";

export const metadata = {
  title: "baam-stock · 研究与验证",
  description: "美股短期研究与预测（仅研究与验证，不构成投资建议）",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: "2rem", lineHeight: 1.6 }}>{children}</body>
    </html>
  );
}
