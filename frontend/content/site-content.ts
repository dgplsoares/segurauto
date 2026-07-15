/**
 * Content provider estático (PT-BR) para a landing page da SegurAuto.
 * Centraliza toda a copy — prepara a migração para um CMS na V2.
 */

export const brand = {
  name: "SegurAuto",
  tagline: "Seguro de auto, resolvido numa conversa.",
};

export const nav = [
  { label: "Como funciona", href: "#como-funciona" },
  { label: "Coberturas", href: "#coberturas" },
  { label: "FAQ", href: "#faq" },
];

export const hero = {
  headline: "O seguro do seu carro começa com uma conversa.",
  subheadline:
    "Fale com o nosso consultor de IA, tire suas dúvidas e receba uma cotação sob medida — sem formulário chato e sem espera.",
  promptExamples: [
    "Quero cotar o seguro do meu HB20…",
    "Meu seguro cobre roubo e furto?",
    "Quanto custa para um Onix 2020?",
    "Tem carro reserva e assistência 24h?",
  ],
  trustBadges: [
    "Dados protegidos (LGPD)",
    "Sem custo para cotar",
    "Resposta em segundos",
  ],
};

export const socialProof = {
  clients: "+120 mil motoristas atendidos",
  rating: "4,9",
  ratingLabel: "de avaliação média",
  partnersLabel: "Seguradoras parceiras",
  partners: ["Aurora Seguros", "Vértice", "Guardião", "Nimbus", "Marévia"],
};

export const howItWorks = {
  title: "Do jeito mais simples: converse, compare, contrate.",
  subtitle: "Três passos para proteger o seu carro sem burocracia.",
  steps: [
    {
      id: "converse",
      icon: "MessagesSquare",
      title: "Converse",
      description:
        "Diga o que você precisa ao consultor de IA. Ele entende seu perfil e o seu veículo numa conversa natural.",
    },
    {
      id: "compare",
      icon: "Scale",
      title: "Compare",
      description:
        "Receba opções das seguradoras parceiras, lado a lado, com preços e coberturas transparentes.",
    },
    {
      id: "contrate",
      icon: "ShieldCheck",
      title: "Contrate",
      description:
        "Escolha o plano ideal e feche em minutos, com todo o suporte que você precisar.",
    },
  ],
};

export const coverages = {
  title: "Coberturas que cuidam de você em cada detalhe.",
  subtitle: "Monte a proteção certa para a sua rotina.",
  items: [
    {
      id: "roubo",
      icon: "Lock",
      title: "Roubo e furto",
      description: "Indenização integral em caso de roubo ou furto do veículo.",
    },
    {
      id: "colisao",
      icon: "CarFront",
      title: "Colisão",
      description: "Cobertura para danos ao seu carro em acidentes de trânsito.",
    },
    {
      id: "terceiros",
      icon: "Users",
      title: "Danos a terceiros",
      description: "Proteção contra danos materiais e corporais a terceiros.",
    },
    {
      id: "assistencia",
      icon: "Wrench",
      title: "Assistência 24h",
      description: "Guincho, chaveiro e socorro elétrico a qualquer hora.",
    },
    {
      id: "reserva",
      icon: "Car",
      title: "Carro reserva",
      description: "Continue se locomovendo enquanto seu carro é reparado.",
    },
    {
      id: "vidros",
      icon: "SprayCan",
      title: "Vidros e faróis",
      description: "Reparo ou troca de para-brisa, vidros, faróis e lanternas.",
    },
  ],
};

export const differentiators = {
  title: "Por que a SegurAuto?",
  subtitle: "Tecnologia a serviço de um seguro mais humano.",
  items: [
    {
      id: "rapidez",
      icon: "Zap",
      title: "Rapidez de verdade",
      description:
        "Cotação em segundos e contratação em minutos, direto pela conversa.",
    },
    {
      id: "ia",
      icon: "Bot",
      title: "Atendimento por IA 24/7",
      description:
        "Um consultor sempre disponível para tirar dúvidas, sem fila e sem espera.",
    },
    {
      id: "comparacao",
      icon: "BarChart3",
      title: "Comparação de preços",
      description:
        "Reunimos as melhores seguradoras para você economizar sem perder cobertura.",
    },
  ],
};

export const testimonials = {
  title: "Quem já dirige tranquilo com a SegurAuto.",
  items: [
    {
      id: "t1",
      name: "Camila Ferreira",
      location: "São Paulo, SP",
      rating: 5,
      quote:
        "Cotei o seguro do meu Onix conversando pelo celular. Em minutos tinha três opções e fechei na hora. Surreal de fácil.",
      avatar:
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=160&h=160&fit=crop&auto=format",
    },
    {
      id: "t2",
      name: "Rafael Souza",
      location: "Belo Horizonte, MG",
      rating: 5,
      quote:
        "O consultor de IA respondeu todas as minhas dúvidas sobre cobertura de terceiros. Sem enrolação e sem letra miúda.",
      avatar:
        "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=160&h=160&fit=crop&auto=format",
    },
    {
      id: "t3",
      name: "Juliana Martins",
      location: "Curitiba, PR",
      rating: 5,
      quote:
        "Precisei de guincho num domingo à noite e a assistência 24h resolveu rapidinho. Vale cada centavo.",
      avatar:
        "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=160&h=160&fit=crop&auto=format",
    },
  ],
};

export const reconversion = {
  title: "Pronto para dirigir mais tranquilo?",
  subtitle:
    "Comece a conversa agora mesmo — leva menos de um minuto para receber sua primeira resposta.",
};

export const faq = {
  title: "Perguntas frequentes",
  subtitle: "Tudo o que você precisa saber antes de começar.",
  items: [
    {
      id: "f1",
      question: "Como funciona a cotação pela conversa?",
      answer:
        "Você conta o que precisa ao nosso consultor de IA, que entende seu perfil e o seu veículo e busca as melhores opções nas seguradoras parceiras. É rápido, natural e sem formulários longos.",
    },
    {
      id: "f2",
      question: "Preciso pagar algo para cotar?",
      answer:
        "Não. A cotação é totalmente gratuita e sem compromisso. Você só paga se decidir contratar um plano.",
    },
    {
      id: "f3",
      question: "Quais coberturas estão disponíveis?",
      answer:
        "Oferecemos roubo e furto, colisão, danos a terceiros, assistência 24h (guincho e chaveiro), carro reserva, vidros e faróis, entre outras. Você monta a proteção ideal para a sua rotina.",
    },
    {
      id: "f4",
      question: "Meus dados estão seguros?",
      answer:
        "Sim. Tratamos seus dados com cuidado e em conformidade com a LGPD. Você tem controle sobre suas informações e só as usamos para oferecer o melhor seguro.",
    },
    {
      id: "f5",
      question: "Em quanto tempo consigo contratar?",
      answer:
        "Depois de escolher o plano ideal, a contratação leva apenas alguns minutos, tudo de forma digital e com suporte a cada passo.",
    },
  ],
};

export const footer = {
  description:
    "A SegurAuto conecta você às melhores seguradoras do Brasil por meio de um consultor de IA. Simples, rápido e transparente.",
  columns: [
    {
      title: "Produto",
      links: [
        { label: "Como funciona", href: "#como-funciona" },
        { label: "Coberturas", href: "#coberturas" },
        { label: "Diferenciais", href: "#diferenciais" },
        { label: "FAQ", href: "#faq" },
      ],
    },
    {
      title: "Empresa",
      links: [
        { label: "Sobre nós", href: "#" },
        { label: "Seguradoras parceiras", href: "#" },
        { label: "Trabalhe conosco", href: "#" },
        { label: "Contato", href: "#" },
      ],
    },
    {
      title: "Legal",
      links: [
        { label: "Privacidade e LGPD", href: "#" },
        { label: "Termos de uso", href: "#" },
        { label: "Política de cookies", href: "#" },
      ],
    },
  ],
  contact: {
    email: "contato@segurauto.com.br",
    phone: "0800 123 4567",
  },
  legal: "SegurAuto é uma empresa fictícia criada para fins de demonstração.",
};

// ===========================================================================
// Conteúdo específico da Home V2 (estética de referência)
// ===========================================================================

export const heroV2 = {
  eyebrow: "Consultor de IA · 24h",
  headline: "Seguro de auto\ncom a gente do seu lado.",
  subheadline: "Rápido, justo e sem burocracia. Comece uma conversa e receba sua cotação.",
  ratingLabel: "Nota Excelente no ReclameBem",
  badges: ["Autorizada e regulada", "Atendimento 24h", "Dados protegidos (LGPD)"],
};

export const mission = {
  title: "Estamos reinventando o seguro de auto.\nDo jeito certo.",
  subtitle:
    "Usamos tecnologia para criar um seguro mais simples, transparente e no seu tempo — feito para você e para o seu bolso.",
  pillars: [
    {
      id: "transparente",
      icon: "Scale",
      title: "Transparente",
      description:
        "Preços e coberturas claros, sem letras miúdas. Você entende exatamente pelo que está pagando.",
    },
    {
      id: "do-seu-lado",
      icon: "ShieldCheck",
      title: "Do seu lado",
      description:
        "Trabalhamos para você, não contra você. Atendimento humano quando precisar e IA quando quiser agilidade.",
    },
    {
      id: "rapido",
      icon: "Zap",
      title: "Rápido de verdade",
      description:
        "Cotação em segundos e contratação em minutos, tudo pela conversa. Sem espera, sem fila.",
    },
  ],
};

export const features = [
  {
    id: "chat",
    screen: "chat" as const,
    title: "Atendimento por IA na velocidade da luz",
    description:
      "Nunca mais fique esperando na linha. Fale com o consultor de IA e tenha respostas em segundos — dúvidas, cotação e suporte, 24 horas por dia.",
  },
  {
    id: "policy",
    screen: "policy" as const,
    title: "Sua apólice no bolso",
    description:
      "Todos os detalhes da sua cobertura e documentos guardados na sua conta. Acesse quando e onde quiser, direto do celular.",
  },
  {
    id: "vehicle",
    screen: "vehicle" as const,
    title: "Altere sua cobertura em segundos",
    description:
      "A vida muda, seu seguro acompanha. Precisa ajustar algo na cobertura? Leva poucos segundos na sua conta.",
  },
  {
    id: "fees",
    screen: "fees" as const,
    title: "Sem taxas de administração",
    description:
      "Nossa tecnologia elimina custos desnecessários. Fez uma alteração? É tudo online, instantâneo e livre de taxas escondidas.",
  },
];

export const coverageTabsIntro = {
  title: "O mais alto nível de cobertura",
  subtitle:
    "Veja rapidamente o que está incluído na nossa proteção completa para o seu carro.",
};

export const deepSection = {
  eyebrow: "Compromisso SegurAuto",
  title: "Direção com propósito",
  subtitle:
    "A cada apólice, apoiamos programas de trânsito mais seguro e compensação de carbono. Dirigir tranquilo também é cuidar do que vem pela frente.",
  cta: "Saiba mais",
};

export const ratings = {
  title: "Atendimento nota 10",
  subtitle:
    "Será que dá para amar uma seguradora? O júri ainda decide — mas estamos bem confiantes.",
  ratingScaleLabel: "Avaliação dos clientes",
  rows: [
    { id: "segurauto", name: "SegurAuto", score: 4.9, highlight: true },
    { id: "c1", name: "Auto Nacional", score: 4.0, highlight: false },
    { id: "c2", name: "ProtegeCar", score: 3.9, highlight: false },
    { id: "c3", name: "Vida & Volante", score: 3.6, highlight: false },
    { id: "c4", name: "SeguraMais", score: 3.4, highlight: false },
    { id: "c5", name: "RodaCerta", score: 3.2, highlight: false },
  ],
  pressLabel: "Destaque na imprensa",
  press: ["O Jornal", "Revista Mobilidade", "Portal Economia", "InovaTech"],
};

export const story = {
  title: "Nossa história",
  text: "Não criamos a SegurAuto porque amávamos seguros. Muito pelo contrário: queríamos mudar como o setor trata as pessoas. Simples assim.",
  cta: "Leia nossa história",
};
