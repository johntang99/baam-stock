import type { ReactNode } from "react";

import "./globals.css";

import { Nav } from "@/components/Nav";
import { getViewer, isFixture } from "@/lib/data";

export const metadata = {
  title: "baam-stock · 研究与验证",
  description: "美股短期研究与预测（内部；不构成投资建议）",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  let viewer = null;
  try {
    viewer = await getViewer();
  } catch {
    viewer = null; // the page itself reports configuration / session problems
  }
  return (
    <html lang="zh-CN">
      <body>
        <Nav viewer={viewer} synthetic={isFixture()} />
        <div className="container">{children}</div>
        <footer className="foot">
          <small>仅限内部团队使用，不对外开放，不构成投资建议。时间显示为美东时间（ET）。</small>
        </footer>
      </body>
    </html>
  );
}
