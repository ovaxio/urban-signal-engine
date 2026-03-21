"use client";

import { useState, type FormEvent } from "react";
import s from "../page.module.css";
import { submitContact } from "@/lib/api";

export default function ContactForm() {
  const [status, setStatus] = useState<"idle" | "sending" | "success" | "error">("idle");

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("sending");
    const fd = new FormData(e.currentTarget);
    const event = fd.get("event") as string;
    const message = fd.get("message") as string;
    try {
      await submitContact({
        nom: fd.get("name") as string,
        email: fd.get("email") as string,
        organisation: fd.get("company") as string,
        message: event ? `[Événement: ${event}] ${message}`.trim() : message,
        source: "Landing",
      });
      setStatus("success");
    } catch {
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div className={s.success}>
        <div className={s.successIcon}>{"✓"}</div>
        <p className={s.successTitle}>Demande reçue.</p>
        <p className={s.successSub}>Vous serez contacté sous 24h.</p>
      </div>
    );
  }

  return (
    // MVP: form requires JS. No action fallback implemented.
    // Acceptable per CLAUDE.md MVP constraints.
    <form onSubmit={handleSubmit} className={s.form}>
      <div className={s.fieldRow}>
        <div className={s.field}>
          <label htmlFor="name" className={s.fieldLabel}>Prénom & Nom</label>
          <input id="name" name="name" type="text" required className={s.fieldInput} />
        </div>
        <div className={s.field}>
          <label htmlFor="email" className={s.fieldLabel}>Email professionnel</label>
          <input id="email" name="email" type="email" required className={s.fieldInput} />
        </div>
      </div>
      <div className={s.fieldRow}>
        <div className={s.field}>
          <label htmlFor="company" className={s.fieldLabel}>Entreprise</label>
          <input id="company" name="company" type="text" required className={s.fieldInput} />
        </div>
        <div className={s.field}>
          <label htmlFor="event" className={s.fieldLabel}>Prochain événement</label>
          <input
            id="event"
            name="event"
            type="text"
            className={s.fieldInput}
            placeholder="Ex : Match OL 15 avril, Groupama Stadium"
          />
        </div>
      </div>
      <div className={s.field}>
        <label htmlFor="message" className={s.fieldLabel}>Message (optionnel)</label>
        <textarea
          id="message"
          name="message"
          rows={3}
          className={s.fieldTextarea}
          placeholder="Zone à couvrir, contexte particulier…"
        />
      </div>
      <button type="submit" className={s.submit} disabled={status === "sending"}>
        {status === "sending" ? "Envoi en cours…" : "Envoyer ma demande"}
      </button>
      {status === "error" && (
        <p className={s.errorMsg}>Une erreur est survenue. Réessayez ou contactez-nous directement.</p>
      )}
    </form>
  );
}
