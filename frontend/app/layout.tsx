import type { Metadata } from "next";
import { Schibsted_Grotesk, IBM_Plex_Mono, Silkscreen } from "next/font/google";
import { DesktopFlag } from "@/components/DesktopFlag";
import "./globals.css";

// Self-hosted at build time (next/font) so the desktop build works offline.
const fontUi = Schibsted_Grotesk({
  subsets: ["latin"],
  variable: "--font-ui",
});
const fontMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});
const fontPixel = Silkscreen({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-pixel",
});

export const metadata: Metadata = {
  title: "Momentum",
  description: "AI agent for Product Managers",
};

// Applies the saved theme before paint to avoid a light→dark flash.
const themeScript = `
(function(){try{
  var t = localStorage.getItem('pmom-theme');
  if(!t){ t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }
  document.documentElement.dataset.theme = t;
}catch(e){}})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fontUi.variable} ${fontMono.variable} ${fontPixel.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="font-sans antialiased">
        <DesktopFlag />
        {children}
      </body>
    </html>
  );
}
