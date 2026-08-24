import { createServerClient, type CookieOptions } from '@supabase/ssr'
import { type NextRequest } from 'next/server'
import { routing } from '@/i18n/routing'

function publicOrigin(request: NextRequest): string {
  const proto = request.headers.get('x-forwarded-proto') ?? 'https'
  const host =
    request.headers.get('x-forwarded-host') ??
    request.headers.get('host') ??
    request.nextUrl.host
  return `${proto}://${host}`
}

const AUTH_PAGES = ['/login', '/signup', '/forgot-password', '/reset-password']

// Strips a locale prefix (e.g. "/it/dashboard" -> "/dashboard") so the
// route-protection checks below stay locale-agnostic. The default locale
// ("en") is unprefixed, so an already-bare path just passes through.
function stripLocale(pathname: string): { locale: string; path: string } {
  for (const locale of routing.locales) {
    if (locale === routing.defaultLocale) continue
    if (pathname === `/${locale}`) return { locale, path: '/' }
    if (pathname.startsWith(`/${locale}/`)) {
      return { locale, path: pathname.slice(locale.length + 1) }
    }
  }
  return { locale: routing.defaultLocale, path: pathname }
}

function withLocale(locale: string, path: string): string {
  return locale === routing.defaultLocale ? path : `/${locale}${path}`
}

export type SessionUpdate = {
  redirectTo: string | null
  cookiesToSet: { name: string; value: string; options: CookieOptions }[]
}

// Decides whether the request needs redirecting for auth/onboarding reasons
// and collects any refreshed Supabase session cookies. Returns plain data
// instead of a NextResponse so the caller (proxy.ts) can apply the cookies
// onto whichever response it ultimately returns (a redirect, or next-intl's
// locale-routing response).
export async function updateSession(request: NextRequest): Promise<SessionUpdate> {
  const collected: SessionUpdate['cookiesToSet'] = []

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? ''
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? ''

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll() {
        return request.cookies.getAll()
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
        collected.push(...cookiesToSet)
      },
    },
  })

  const {
    data: { user },
  } = await supabase.auth.getUser()

  const origin = publicOrigin(request)
  const { locale, path } = stripLocale(request.nextUrl.pathname)

  // Protect /dashboard
  if (!user && path.startsWith('/dashboard')) {
    return { redirectTo: `${origin}${withLocale(locale, '/login')}`, cookiesToSet: collected }
  }

  // Don't show signed-in users the auth pages — unless they're in the middle
  // of password recovery (handled inside /reset-password).
  if (user && AUTH_PAGES.includes(path)) {
    return { redirectTo: `${origin}${withLocale(locale, '/dashboard')}`, cookiesToSet: collected }
  }

  // Force onboarding before dashboard.
  if (user && path.startsWith('/dashboard')) {
    const { data: kin } = await supabase
      .from('users')
      .select('onboarding_completed')
      .eq('auth_user_id', user.id)
      .maybeSingle()
    if (!kin || kin.onboarding_completed !== true) {
      return { redirectTo: `${origin}${withLocale(locale, '/onboarding')}`, cookiesToSet: collected }
    }
  }

  // Conversely, if onboarding is done, /onboarding bounces to /dashboard.
  if (user && path.startsWith('/onboarding')) {
    const { data: kin } = await supabase
      .from('users')
      .select('onboarding_completed')
      .eq('auth_user_id', user.id)
      .maybeSingle()
    if (kin?.onboarding_completed === true) {
      return { redirectTo: `${origin}${withLocale(locale, '/dashboard')}`, cookiesToSet: collected }
    }
  }

  return { redirectTo: null, cookiesToSet: collected }
}
