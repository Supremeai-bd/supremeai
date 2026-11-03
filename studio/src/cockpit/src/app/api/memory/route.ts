import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { logActivity } from "@/lib/settings";
import type { MemoryNoteData } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

function toData(r: {
  id: string;
  kind: string;
  title: string;
  content: string;
  tags: string;
  source: string;
  pinned: boolean;
  createdAt: Date;
  updatedAt: Date;
}): MemoryNoteData {
  return {
    id: r.id,
    kind: r.kind,
    title: r.title,
    content: r.content,
    tags: r.tags ? r.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
    source: r.source,
    pinned: r.pinned,
    createdAt: r.createdAt.toISOString(),
    updatedAt: r.updatedAt.toISOString(),
  };
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const q = url.searchParams.get("q")?.trim();
  const kind = url.searchParams.get("kind")?.trim();
  const where = {
    ...(q ? { OR: [{ title: { contains: q } }, { content: { contains: q } }, { tags: { contains: q } }] } : {}),
    ...(kind && kind !== "all" ? { kind } : {}),
  };
  const rows = await db.memoryNote.findMany({
    where,
    orderBy: [{ pinned: "desc" }, { updatedAt: "desc" }],
    take: 100,
  });
  const counts = await db.memoryNote.groupBy({ by: ["kind"], _count: { kind: true } });
  return NextResponse.json({
    notes: rows.map(toData),
    stats: Object.fromEntries(counts.map((c) => [c.kind, c._count.kind])),
    total: rows.length,
  });
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { title?: string; content?: string; kind?: string; tags?: string; pinned?: boolean } | null;
  if (!body?.title?.trim() || !body?.content?.trim()) {
    return NextResponse.json({ error: "title and content are required" }, { status: 400 });
  }
  const note = await db.memoryNote.create({
    data: {
      title: body.title.trim().slice(0, 200),
      content: body.content.trim().slice(0, 8000),
      kind: ["fact", "decision", "lesson", "insight", "sync"].includes(body.kind ?? "") ? body.kind! : "fact",
      tags: (body.tags ?? "").slice(0, 300),
      pinned: Boolean(body.pinned),
      source: "manual",
    },
  });
  await logActivity("memory", "info", `Memory: ${note.title}`, note.content.slice(0, 120), { kind: note.kind });
  return NextResponse.json({ note: toData(note) }, { status: 201 });
}

export async function PATCH(request: Request) {
  const body = (await request.json().catch(() => null)) as { id?: string; pinned?: boolean; title?: string; content?: string; tags?: string; kind?: string } | null;
  if (!body?.id) return NextResponse.json({ error: "id required" }, { status: 400 });
  const data: Record<string, unknown> = {};
  if (typeof body.pinned === "boolean") data.pinned = body.pinned;
  if (body.title) data.title = body.title.slice(0, 200);
  if (body.content) data.content = body.content.slice(0, 8000);
  if (typeof body.tags === "string") data.tags = body.tags.slice(0, 300);
  if (body.kind && ["fact", "decision", "lesson", "insight", "sync"].includes(body.kind)) data.kind = body.kind;
  const note = await db.memoryNote.update({ where: { id: body.id }, data });
  return NextResponse.json({ note: toData(note) });
}

export async function DELETE(request: Request) {
  const url = new URL(request.url);
  const id = url.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  await db.memoryNote.delete({ where: { id } });
  return NextResponse.json({ ok: true });
}
