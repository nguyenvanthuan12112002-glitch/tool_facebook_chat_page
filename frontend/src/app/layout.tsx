import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Omnichannel Page Sync - Sales Management",
  description: "Synchronize your Facebook pages effortlessly with our Omnichannel system.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
