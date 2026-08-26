// True app-root 404 — only reached for a request that never makes it into
// the [locale] segment tree at all (e.g. malformed paths outside the
// middleware's matcher in src/proxy.ts). There is no app/layout.tsx above
// this file — app/[locale]/layout.tsx is the *only* place <html>/<body> are
// rendered for normal traffic — so this file has to supply its own minimal
// document shell rather than relying on a shared root layout. Almost every
// real 404 a visitor hits instead resolves inside app/[locale]/not-found.tsx.
import Link from "next/link";
import "./globals.css";

export default function RootNotFound() {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col items-center justify-center p-6 bg-background text-foreground">
        <div className="w-full max-w-sm text-center">
          <h1 className="text-2xl font-bold tracking-tight mb-2">Page not found</h1>
          <p className="text-sm text-muted-foreground mb-8">
            The page you&apos;re looking for doesn&apos;t exist or may have moved.
          </p>
          <Link
            href="/"
            className="inline-block w-full h-10 leading-10 rounded-md bg-foreground text-background font-medium"
          >
            Back home
          </Link>
        </div>
      </body>
    </html>
  );
}
