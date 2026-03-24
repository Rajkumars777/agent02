import type { Metadata } from "next";
import { Outfit, Geist_Mono, Rajdhani, Exo_2 } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
  weight: ["300", "400", "500", "700", "900"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const rajdhani = Rajdhani({
  variable: "--font-rajdhani",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const exo2 = Exo_2({
  variable: "--font-exo2",
  subsets: ["latin"],
  weight: ["300", "400"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "Nexus | Next-Gen AI Agent",
  description: "Experience the power of an intelligent workflow automation system. Powered by advanced autonomous reasoning.",
};

import TauriProvider from "@/components/TauriProvider";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${outfit.variable} ${geistMono.variable} ${rajdhani.variable} ${exo2.variable} antialiased selection:text-white`}
      >
        <TauriProvider>
          {children}
        </TauriProvider>
      </body>
    </html>
  );
}
