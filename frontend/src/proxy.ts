import { NextResponse, type NextRequest } from 'next/server'
import createIntlMiddleware from 'next-intl/middleware'
import { routing } from '@/i18n/routing'
import { updateSession } from '@/lib/supabase/middleware'

const intlMiddleware = createIntlMiddleware(routing)

function publicOrigin(request: NextRequest): string {
  const proto = request.headers.get('x-forwarded-proto') ?? 'https'
  const host =
    request.headers.get('x-forwarded-host') ??
    request.headers.get('host') ??
    request.nextUrl.host
  return `${proto}://${host}`
}

export async function proxy(request: NextRequest) {
  // FAIL-SAFE: if Supabase ever redirects an auth code to the root path,
  // forward it to /auth/callback on the public origin (not the container's
  // internal 0.0.0.0:8080 host). Runs before locale routing since the code
  // param can land on either "/" or "/it".
  const code = request.nextUrl.searchParams.get('code')
  const pathname = request.nextUrl.pathname
  if (code && (pathname === '/' || pathname === '/it')) {
    return NextResponse.redirect(`${publicOrigin(request)}/auth/callback?code=${code}`)
  }

  // Auth/onboarding gate first — locale-agnostic (strips any /it prefix
  // internally) so a redirect to /login or /dashboard preserves whichever
  // locale the visitor was on.
  const { redirectTo, cookiesToSet } = await updateSession(request)
  if (redirectTo) {
    return NextResponse.redirect(redirectTo)
  }

  // No auth redirect needed — hand off to next-intl for locale detection/
  // routing, then re-apply any refreshed Supabase session cookies onto
  // whichever response it produces.
  const response = intlMiddleware(request)
  cookiesToSet.forEach(({ name, value, options }) => {
    response.cookies.set(name, value, options)
  })
  return response
}

export const config = {
  matcher: [
    // icon/apple-icon/opengraph-image/robots.txt/sitemap.xml are root-level
    // metadata routes (app/icon.tsx etc.) living outside the [locale]
    // segment tree. Without excluding them here, next-intl's middleware
    // rewrites requests for them into /[locale]/icon and similar, where no
    // such route exists — 404ing every one of them, including in production.
    '/((?!_next/static|_next/image|favicon.ico|icon|apple-icon|opengraph-image|robots.txt|sitemap.xml|api|auth/callback|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
