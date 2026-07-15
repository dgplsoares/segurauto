"use client";

import { Instagram, Linkedin, Facebook, Mail, Phone } from "lucide-react";
import { brand, footer } from "../../content/site-content";

export function V2Footer() {
  return (
    <footer className="bg-primary text-primary-foreground">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div>
            <span className="font-display text-2xl font-semibold tracking-tight">
              segur<span className="text-accent">auto</span>
            </span>
            <p className="mt-4 max-w-xs text-sm text-primary-foreground/70">
              {footer.description}
            </p>
            <div className="mt-6 flex gap-3">
              {[Instagram, Linkedin, Facebook].map((Icon, i) => (
                <a
                  key={i}
                  href="#"
                  className="flex size-10 items-center justify-center rounded-full border border-primary-foreground/20 text-primary-foreground/80 transition-colors hover:bg-accent hover:text-accent-foreground hover:border-transparent"
                  aria-label="Rede social"
                >
                  <Icon className="size-4" />
                </a>
              ))}
            </div>
          </div>

          {footer.columns.map((col) => (
            <div key={col.title}>
              <h3 className="font-display text-lg font-semibold">{col.title}</h3>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      className="text-sm text-primary-foreground/70 transition-colors hover:text-primary-foreground"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-4 border-t border-primary-foreground/15 pt-8 text-sm text-primary-foreground/70 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <a href={`mailto:${footer.contact.email}`} className="flex items-center gap-2">
              <Mail className="size-4" /> {footer.contact.email}
            </a>
            <span className="flex items-center gap-2">
              <Phone className="size-4" /> {footer.contact.phone}
            </span>
          </div>
          <p>
            © {new Date().getFullYear()} {brand.name}. {footer.legal}
          </p>
        </div>
      </div>
    </footer>
  );
}
