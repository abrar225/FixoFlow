"use client";
import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);
export function MotionScene({ children }: { children: React.ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = gsap.matchMedia();
    const context = gsap.context(() => {
      media.add(
        {
          motion: "(prefers-reduced-motion: no-preference)",
          desktop: "(min-width: 801px)",
        },
        (match) => {
          if (!match.conditions?.motion) return;
          const titles = root.current?.querySelectorAll("[data-title]");
          if (titles?.length)
            gsap.from(titles, {
              yPercent: 110,
              duration: 1.05,
              stagger: 0.1,
              ease: "power4.out",
              clearProps: "transform",
            });
          const entrances = root.current?.querySelectorAll("[data-enter]");
          if (entrances?.length)
            gsap.from(entrances, {
              opacity: 0,
              y: 12,
              duration: 0.7,
              stagger: 0.07,
              delay: 0.25,
              clearProps: "all",
            });
          const stage = root.current?.querySelector("[data-stage]");
          if (stage)
            gsap.from(stage, {
              opacity: 0,
              scale: 0.94,
              rotate: 3,
              duration: 1.1,
              delay: 0.2,
              ease: "power3.out",
              clearProps: "all",
            });
          const desktop = window.matchMedia("(min-width: 801px)").matches;
          const hero = root.current?.querySelector(".hero");
          const heroDemo = hero?.querySelector(".voice-demo");
          if (hero && heroDemo) {
            gsap.fromTo(
              heroDemo,
              { y: 0, x: 0, rotate: 0 },
              {
                y: desktop ? -110 : -28,
                x: desktop ? -24 : 0,
                rotate: desktop ? -5 : 0,
                ease: "none",
                scrollTrigger: {
                  trigger: hero,
                  start: "top top",
                  end: "bottom top",
                  scrub: 0.8,
                },
              },
            );
          }
          const words = root.current?.querySelectorAll(
            ".everyday-words > span",
          );
          words?.forEach((word, index) =>
            gsap.fromTo(
              word,
              { y: index % 2 ? 25 : -15, rotate: index % 2 ? 3 : -2 },
              {
                y: 0,
                rotate: 0,
                ease: "none",
                scrollTrigger: {
                  trigger: word.parentElement,
                  start: "top 95%",
                  end: "top 45%",
                  scrub: 0.7,
                },
              },
            ),
          );
          root.current
            ?.querySelectorAll(".voice-demo-full .demo-scene")
            .forEach((scene) => {
              gsap.fromTo(
                scene,
                { xPercent: desktop ? -3 : 0, y: 15 },
                {
                  xPercent: desktop ? 3 : 0,
                  y: -15,
                  ease: "none",
                  scrollTrigger: {
                    trigger: scene.parentElement,
                    start: "top bottom",
                    end: "bottom top",
                    scrub: 0.8,
                  },
                },
              );
            });
          root.current
            ?.querySelectorAll(".dictionary-visual, .history-visual")
            .forEach((art, index) => {
              gsap.fromTo(
                art,
                { y: 35, rotate: index % 2 ? -7 : 7 },
                {
                  y: -18,
                  rotate: index % 2 ? -2 : 2,
                  ease: "none",
                  scrollTrigger: {
                    trigger: art.parentElement,
                    start: "top 95%",
                    end: "bottom 20%",
                    scrub: 0.9,
                  },
                },
              );
            });
          root.current
            ?.querySelectorAll(".privacy-device")
            .forEach((device) => {
              gsap.fromTo(
                device,
                { y: 30, rotate: -4 },
                {
                  y: -25,
                  rotate: 3,
                  ease: "none",
                  scrollTrigger: {
                    trigger: device.parentElement,
                    start: "top bottom",
                    end: "bottom top",
                    scrub: 0.8,
                  },
                },
              );
            });
          root.current?.querySelectorAll(".closing-cta h2").forEach((title) => {
            gsap.fromTo(
              title,
              { y: 55 },
              {
                y: -10,
                ease: "none",
                scrollTrigger: {
                  trigger: title.parentElement,
                  start: "top 90%",
                  end: "center center",
                  scrub: 0.7,
                },
              },
            );
          });
          root.current?.querySelectorAll("[data-scroll-art]").forEach((art) => {
            gsap.fromTo(
              art,
              { rotate: -8, y: 25 },
              {
                rotate: 6,
                y: -25,
                ease: "none",
                scrollTrigger: {
                  trigger: art,
                  start: "top bottom",
                  end: "bottom top",
                  scrub: 1,
                },
              },
            );
          });
        },
      );
    }, root);
    return () => {
      media.revert();
      context.revert();
    };
  }, []);
  return <div ref={root}>{children}</div>;
}
