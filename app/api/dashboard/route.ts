import { NextRequest, NextResponse } from "next/server"

type Platform = "telegram" | "discord" | "x" | "weekly_report" | "weekly_suggestions"
type Community = "SOSOVALUE" | "SODEX"

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_SECRET_KEY = process.env.SUPABASE_SECRET_KEY

function ensureSupabaseConfig() {
  if (!SUPABASE_URL || !SUPABASE_SECRET_KEY) {
    throw new Error("Missing SUPABASE_URL or SUPABASE_SECRET_KEY")
  }
}

async function supabaseQuery(table: string, query: string) {
  ensureSupabaseConfig()
  const response = await fetch(`${SUPABASE_URL}/rest/v1/${table}?${query}`, {
    headers: {
      apikey: SUPABASE_SECRET_KEY!,
      Authorization: `Bearer ${SUPABASE_SECRET_KEY!}`,
      Accept: "application/json",
    },
    cache: "no-store",
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Supabase ${response.status}: ${text}`)
  }

  return response.json()
}

function toTelegramPayload(row: any) {
  const rawPayload = row.raw_payload || {}
  const summary = row.summary || rawPayload.analysis?.summary || ""
  const questionsSource = row.questions || rawPayload.analysis?.questions || []
  const questions = Array.isArray(questionsSource)
    ? questionsSource.map((q: any) => (typeof q === "string" ? q : q?.question || q?.text || "")).filter(Boolean)
    : []
  const aiAnalysis = `Summary: ${summary}\n\nTop Community Questions:\n${questions.map((q: string, i: number) => `${i + 1}. ${q}`).join("\n")}`

  return {
    date: row.report_date,
    totals: {
      messages: row.total_messages ?? rawPayload.totals?.messages ?? 0,
      users: row.active_users ?? rawPayload.totals?.users ?? 0,
    },
    active_hours_sgt: row.active_hours_sgt || rawPayload.active_hours_sgt || {},
    ai_analysis: aiAnalysis,
    sections: row.sections || rawPayload.sections || [],
    leaderboards: {
      community_users: row.community_users || rawPayload.leaderboards?.community_users || [],
      moderators: row.moderators || rawPayload.leaderboards?.moderators || [],
    },
  }
}

function normalizeDiscordCategory(key: string) {
  const raw = key.toLowerCase().trim()
  if (raw.includes("retail")) return "retail"
  if (raw.includes("trading")) return "trading"
  if (raw.includes("ticket") || raw.includes("support")) return "tickets"
  if (raw.includes("dev")) return "dev"
  return raw
}

function normalizeSectionReports(value: any) {
  const normalized: Record<string, { summary: string; questions: string[] }> = {
    retail: { summary: "", questions: [] },
    trading: { summary: "", questions: [] },
    tickets: { summary: "", questions: [] },
    dev: { summary: "", questions: [] },
  }

  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [rawKey, rawSection] of Object.entries(value)) {
      const key = normalizeDiscordCategory(rawKey)
      if (!normalized[key]) continue
      const section = rawSection as any
      const questions = Array.isArray(section?.questions)
        ? section.questions.map((q: any) => (typeof q === "string" ? q : q?.question || q?.text || "")).filter(Boolean)
        : []
      normalized[key] = {
        summary: typeof section?.summary === "string" ? section.summary : "",
        questions,
      }
    }
  }

  return normalized
}

function toDiscordPayload(row: any) {
  const rawPayload = row.raw_payload || {}
  const vitals = rawPayload.vitals || {}
  return {
    date: row.report_date,
    vitals: {
      total_messages: row.total_messages ?? vitals.total_messages ?? 0,
      active_users: row.active_users ?? vitals.active_users ?? vitals.active_users_count ?? 0,
    },
    hourly_activity: row.hourly_activity || rawPayload.hourly_activity || {},
    reports: normalizeSectionReports(row.reports || rawPayload.reports || {}),
  }
}

function normalizeXTopicKey(key: string) {
  const compact = key.toLowerCase().replace(/[\s_-]/g, "")
  if (compact.includes("sosovalue")) return "sosovalue"
  if (compact.includes("sodex")) return "sodex"
  if (compact.includes("ssi")) return "ssi"
  return compact
}

function normalizeXTopicObject(value: any) {
  const normalized = {
    sosovalue: "",
    sodex: "",
    ssi: "",
  } as Record<string, any>

  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [rawKey, rawValue] of Object.entries(value)) {
      const key = normalizeXTopicKey(rawKey)
      normalized[key] = rawValue
    }
  }

  return normalized
}

function toXPayload(row: any) {
  const rawPayload = row.raw_payload || {}
  const summary = normalizeXTopicObject(row.summary || rawPayload.summary || {})
  const topQuestions = normalizeXTopicObject(row.top_questions || rawPayload.top_questions || {})
  const posts =
    row.top_engaged_posts ||
    rawPayload.top_engaged_posts ||
    rawPayload["Top poster username, post content, engagement, post link on that date with the highest engagement, atleast 3 posts"] ||
    []

  return {
    date: row.report_date,
    summary: {
      sosovalue: typeof summary.sosovalue === "string" ? summary.sosovalue : "",
      sodex: typeof summary.sodex === "string" ? summary.sodex : "",
      ssi: typeof summary.ssi === "string" ? summary.ssi : "",
    },
    top_questions: {
      sosovalue: Array.isArray(topQuestions.sosovalue) ? topQuestions.sosovalue : [],
      sodex: Array.isArray(topQuestions.sodex) ? topQuestions.sodex : [],
      ssi: Array.isArray(topQuestions.ssi) ? topQuestions.ssi : [],
    },
    top_engaged_posts: Array.isArray(posts) ? posts : [],
    timestamp: row.captured_at || null,
  }
}

function toWeeklyReportPayload(row: any) {
  const rawPayload = row.raw_payload || {}
  return {
    date: row.report_date,
    reports: normalizeSectionReports(row.reports || rawPayload.reports || {}),
  }
}

function toWeeklySuggestionsPayload(row: any) {
  return {
    date: row.report_date,
    team_suggestions: row.team_suggestions || [],
  }
}

function dateQuery(date: string, allowFallback: boolean) {
  if (allowFallback) {
    return `report_date=lte.${encodeURIComponent(date)}&order=report_date.desc&limit=1`
  }
  return `report_date=eq.${encodeURIComponent(date)}&limit=1`
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const platform = searchParams.get("platform") as Platform | null
    const date = searchParams.get("date")
    const community = searchParams.get("community") as Community | null
    const allowFallback = searchParams.get("fallback") === "latest"

    if (!platform || !date) {
      return NextResponse.json({ error: "Missing platform or date" }, { status: 400 })
    }

    let data: any[] = []

    if (platform === "telegram") {
      if (!community) {
        return NextResponse.json({ error: "Missing community for telegram" }, { status: 400 })
      }
      data = await supabaseQuery(
        "telegram_daily_reports",
        `select=*&community=eq.${encodeURIComponent(community)}&${dateQuery(date, allowFallback)}`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toTelegramPayload(data[0]))
    }

    if (platform === "discord") {
      data = await supabaseQuery(
        "discord_daily_reports",
        `select=*&${dateQuery(date, allowFallback)}`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toDiscordPayload(data[0]))
    }

    if (platform === "x") {
      data = await supabaseQuery(
        "x_daily_reports",
        `select=*&${dateQuery(date, allowFallback)}`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toXPayload(data[0]))
    }

    if (platform === "weekly_report") {
      data = await supabaseQuery(
        "weekly_reports",
        `select=*&${dateQuery(date, allowFallback)}`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toWeeklyReportPayload(data[0]))
    }

    if (platform === "weekly_suggestions") {
      data = await supabaseQuery(
        "weekly_suggestions",
        `select=*&${dateQuery(date, allowFallback)}`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toWeeklySuggestionsPayload(data[0]))
    }

    return NextResponse.json({ error: "Unsupported platform" }, { status: 400 })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
