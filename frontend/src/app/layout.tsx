import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

// shadcn's theme reads the font from --font-sans.
const geistSans = Geist({ variable: "--font-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Appeal Agent",
  description:
    "An AI agent that drafts health insurance appeals with plan citations, for a human to review.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full bg-background antialiased`}
    >
      <body className="flex min-h-full flex-col bg-muted/40">
        <TooltipProvider>
          <header className="border-b bg-background">
            <div className="mx-auto flex h-12 max-w-[1600px] items-center justify-between px-4">
              <Link href="/" className="font-semibold tracking-tight">
                Appeal Agent
              </Link>
              <span className="text-xs text-muted-foreground">
                Synthetic data from a fictional insurer. Drafts are never sent.
              </span>
            </div>
          </header>
          <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-4">{children}</main>
          <Toaster />
        </TooltipProvider>
      </body>
    </html>
  );
}
