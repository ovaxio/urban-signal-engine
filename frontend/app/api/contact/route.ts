import { NextRequest, NextResponse } from "next/server";

// TODO: Integrate Resend or similar for email delivery
// TODO: Forward to CRM or Notion database

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { name, email, company, event, message } = body;

    if (!name || !email || !company) {
      return NextResponse.json(
        { error: "Champs obligatoires manquants" },
        { status: 400 },
      );
    }

    console.log("[contact-form] Nouvelle demande:", {
      name,
      email,
      company,
      event: event || "(non renseigné)",
      message: message || "(vide)",
      ts: new Date().toISOString(),
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    if (error instanceof SyntaxError) {
      return NextResponse.json(
        { error: "Requête invalide" },
        { status: 400 },
      );
    }
    console.error("[contact-form] Erreur inattendue:", error);
    return NextResponse.json(
      { error: "Erreur interne" },
      { status: 500 },
    );
  }
}
