"use client";

// LP portada do protótipo do frontend (Fase 5c), ligada ao BFF real via lib/api.ts.
// O fluxo prompt-first (LeadFlowProvider) e todas as seções v2 são Client Components a partir daqui.
import { useEffect } from "react";

import { Faq } from "@/components/faq";
import { ChatPanel } from "@/components/chat-panel";
import { OtpModal } from "@/components/otp-modal";
import { PreSignupModal } from "@/components/pre-signup-modal";
import { SupportWidget } from "@/components/support-widget";
import { V2CoverageTabs } from "@/components/v2/v2-coverage-tabs";
import { V2Deep } from "@/components/v2/v2-deep";
import { V2Features } from "@/components/v2/v2-features";
import { V2Footer } from "@/components/v2/v2-footer";
import { V2Header } from "@/components/v2/v2-header";
import { V2Hero } from "@/components/v2/v2-hero";
import { V2Mission } from "@/components/v2/v2-mission";
import { V2Ratings } from "@/components/v2/v2-ratings";
import { V2Reconversion } from "@/components/v2/v2-reconversion";
import { V2Story } from "@/components/v2/v2-story";
import { track } from "@/lib/analytics";
import { LeadFlowProvider } from "@/lib/lead-flow-context";

export default function Home() {
  useEffect(() => {
    track("lp_view");
  }, []);

  return (
    <LeadFlowProvider>
      <div className="min-h-screen bg-background text-foreground">
        <V2Header />
        <main>
          <V2Hero />
          <V2Mission />
          <V2Features />
          <V2CoverageTabs />
          <V2Deep />
          <V2Ratings />
          <V2Story />
          <Faq />
          <V2Reconversion />
        </main>
        <V2Footer />

        {/* Fluxo prompt-first (agora ligado ao BFF real) */}
        <PreSignupModal />
        <OtpModal />
        <ChatPanel />

        {/* Suporte flutuante */}
        <SupportWidget />
      </div>
    </LeadFlowProvider>
  );
}
