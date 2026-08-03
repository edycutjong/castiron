import { CloudOff, FileAudio2, Siren } from "lucide-react";
import { Reveal } from "@/components/reveal";

const FAILURES = [
  {
    icon: CloudOff,
    title: "Vendors go dark without notice",
    body: "TTS providers throttle, return 500s, and disappear mid-render. The vendor call is the one brittle joint in every generative-media pipeline.",
  },
  {
    icon: Siren,
    title: "One outage kills the whole episode",
    body: "A naive pipeline drops everything with it — narration, music, cover, the entire run. On a schedule, that's dead air for your daily brief or podcast.",
  },
  {
    icon: FileAudio2,
    title: "Nothing proves the file is untouched",
    body: "Once an episode is produced, most pipelines can't show it wasn't silently altered afterward. No tamper-evidence from render to storage.",
  },
];

export function Problem() {
  return (
    <section id="problem" className="relative overflow-hidden">
      <div className="bg-blueprint-fine absolute inset-0 opacity-60" aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-5 py-24 sm:px-8 md:py-32">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:gap-20">
          <div>
            <Reveal>
              <p className="runbook-label">01 / The failure mode</p>
              <h2 className="mt-5 font-display text-3xl font-black uppercase leading-[1.08] tracking-tight text-fg sm:text-4xl lg:text-[2.75rem]">
                Generative pipelines break in{" "}
                <span className="text-ember-gradient">exactly one place</span> that matters.
              </h2>
              <p className="mt-6 max-w-md text-base leading-relaxed text-iron-text">
                The vendor call. Everything upstream of it is your code; everything downstream is
                your reputation. CastIron was built for the moment between the two — when the
                provider you paid for simply stops answering.
              </p>
              <div className="hazard mt-8 h-1.5 w-36 rounded-full opacity-70" aria-hidden="true" />
            </Reveal>
          </div>

          <ul className="space-y-4">
            {FAILURES.map((f, i) => (
              <Reveal as="li" key={f.title} delay={i * 120}>
                <div className="plate plate-hover group flex gap-5 rounded-xl p-6">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-danger/30 bg-danger/10 text-danger transition-transform duration-300 group-hover:scale-110">
                    <f.icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="font-display text-base font-bold text-fg">{f.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-iron-text">{f.body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
            <Reveal as="li" delay={360}>
              <p className="px-2 pt-2 font-mono text-xs uppercase tracking-[0.18em] text-forge-400">
                &gt; CastIron treats provider failure as the expected case — not the exception.
              </p>
            </Reveal>
          </ul>
        </div>
      </div>
    </section>
  );
}
