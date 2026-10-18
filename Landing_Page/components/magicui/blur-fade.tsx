"use client";
// Adapted from Magic UI Blur Fade (MIT), https://magicui.design/r/blur-fade.json.
// Uses the existing Framer Motion dependency, semantic content, and reduced motion.
import { motion, useReducedMotion } from "framer-motion";
export function BlurFade({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={false}
      animate={{
        opacity: [0.6, 1],
        filter: reduced ? "none" : ["blur(3px)", "blur(0px)"],
      }}
      transition={{ duration: reduced ? 0 : 0.35, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
