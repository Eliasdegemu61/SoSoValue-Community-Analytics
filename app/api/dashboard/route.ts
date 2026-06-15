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
  const summary = row.summary || ""
  const questions = Array.isArray(row.questions) ? row.questions : []
  const aiAnalysis = `Summary: ${summary}\n\nTop Community Questions:\n${questions.map((q: string, i: number) => `${i + 1}. ${q}`).join("\n")}`

  return {
    date: row.report_date,
    totals: {
      messages: row.total_messages ?? 0,
      users: row.active_users ?? 0,
    },
    active_hours_sgt: row.active_hours_sgt || {},
    ai_analysis: aiAnalysis,
    sections: row.sections || [],
    leaderboards: {
      community_users: row.community_users || [],
      moderators: row.moderators || [],
    },
  }
}

function toDiscordPayload(row: any) {
  return {
    vitals: {
      total_messages: row.total_messages ?? 0,
      active_users: row.active_users ?? 0,
    },
    hourly_activity: row.hourly_activity || {},
    reports: row.reports || {},
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
  return {
    reports: row.reports || {},
  }
}

function toWeeklySuggestionsPayload(row: any) {
  return {
    team_suggestions: row.team_suggestions || [],
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const platform = searchParams.get("platform") as Platform | null
    const date = searchParams.get("date")
    const community = searchParams.get("community") as Community | null

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
        `select=*&community=eq.${encodeURIComponent(community)}&report_date=eq.${encodeURIComponent(date)}&limit=1`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toTelegramPayload(data[0]))
    }

    if (platform === "discord") {
      data = await supabaseQuery(
        "discord_daily_reports",
        `select=*&report_date=eq.${encodeURIComponent(date)}&limit=1`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toDiscordPayload(data[0]))
    }

    if (platform === "x") {
      data = await supabaseQuery(
        "x_daily_reports",
        `select=*&report_date=eq.${encodeURIComponent(date)}&limit=1`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toXPayload(data[0]))
    }

    if (platform === "weekly_report") {
      data = await supabaseQuery(
        "weekly_reports",
        `select=*&report_date=eq.${encodeURIComponent(date)}&limit=1`
      )
      if (!data.length) return NextResponse.json({ error: "Not found" }, { status: 404 })
      return NextResponse.json(toWeeklyReportPayload(data[0]))
    }

    if (platform === "weekly_suggestions") {
      data = await supabaseQuery(
        "weekly_suggestions",
        `select=*&report_date=eq.${encodeURIComponent(date)}&limit=1`
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
