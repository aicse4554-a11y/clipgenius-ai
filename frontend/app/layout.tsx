import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "ClipGenius AI", description: "Free local-first AI video clipping studio" };
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}