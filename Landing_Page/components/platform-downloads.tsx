"use client";
import { useEffect, useState } from "react";
import { Download, Monitor, Check } from "lucide-react";
import releases from "@/lib/releases.generated.json";
import { AppleLogo } from "./apple-logo";

export function PlatformDownloads() {
  const [selected, setSelected] = useState("macos");
  const [detected, setDetected] = useState("");
  useEffect(() => {
    const system = navigator.userAgent.toLowerCase();
    const platform = system.includes("windows") ? "windows" : system.includes("linux") && !system.includes("android") ? "linux" : system.includes("macintosh") ? "macos" : "";
    if (platform) { setSelected(platform); setDetected(platform); }
  }, []);
  const current = releases.platforms.find(p => p.id === selected)!;
  const steps = current.id === "windows" ? [
    ["Check the essentials.", "Use an x64 Windows PC with WebView2 and the Microsoft Visual C++ runtime installed. Windows 11 is the target; Windows 10 22H2 remains a compatibility target."],
    ["Run the setup file.", "Open the downloaded setup and install for your user account. This preview is unsigned; only proceed with software you trust."],
    ["Give your voice a place to land.", "Open Fixo Flow, allow desktop microphone access, configure your two shortcuts in Settings, then click a text field and dictate."]
  ] : current.id === "linux" ? [
    ["Choose an X11 desktop.", "Use Ubuntu 24.04 x64 in an X11 session for global shortcuts and automatic paste. Other distributions and Wayland need further work."],
    ["Open the Debian package.", "Open the downloaded .deb in your package installer. It installs Fixo Flow and resolves its declared system dependencies."],
    ["Find your flow.", "Launch Fixo Flow from the applications menu, check the microphone and shortcuts, then dictate into a text field. Modifier shortcuts are recommended."]
  ] : [
    ["Open the disk image.", "Open the Mac DMG and drag Fixo Flow into Applications."],
    ["Allow the three permissions.", "Open Fixo Flow and allow Microphone, Accessibility and Input Monitoring in System Settings."],
    ["Make it yours.", "Restart the app, configure hold-to-talk and hands-free shortcuts, then click a text field and speak."]
  ];
  return <section className="platform-downloads shell" id="choose-system" aria-labelledby="platform-title">
    <div className="section-heading"><div><p className="section-caption">A place for every voice</p><h2 id="platform-title">Choose your computer.</h2></div><p>Fixo Flow {releases.version}. English recognition runs locally. Each package includes its speech model.</p></div>
    <div className="platform-choices" role="group" aria-label="Operating system">
      {releases.platforms.map(platform => <button key={platform.id} type="button" className={`platform-choice ${selected === platform.id ? "selected" : ""}`} aria-pressed={selected === platform.id} onClick={() => setSelected(platform.id)}>
        {platform.id === "macos" ? <AppleLogo size={26} /> : <Monitor size={26} aria-hidden="true" />}
        <span className="platform-name">{platform.name}</span><span>{platform.architecture}</span>
        <span className="platform-channel">{platform.available ? platform.channel : "In preparation"}{detected === platform.id ? " · your system" : ""}</span>
        {selected === platform.id && <Check className="platform-selected" size={20} aria-hidden="true" />}
      </button>)}
    </div>
    <div className="platform-detail" aria-live="polite">
      <div><h3>{current.name} · {current.architecture}</h3><p>{current.requirements}</p><p>{current.notes}</p><p className="platform-size">{current.bytes ? `${Math.ceil(current.bytes / 1024 / 1024)} MiB download · ` : ""}Processing speed and memory depend on your hardware. A dedicated GPU is optional.</p></div>
      {current.available && current.filename ? <a className="button" href={`/downloads/${current.filename}`} download><Download size={18} /> Download for {current.name}</a> : <span className="platform-pending">Installer not available yet</span>}
    </div>
    <div className="platform-install-guide"><h3>Get started on {current.name}</h3><ol>{steps.map(([title,text]) => <li key={title}><strong>{title}</strong><p>{text}</p></li>)}</ol>{current.id === "windows" && <p>Runtime help: <a href="https://developer.microsoft.com/microsoft-edge/webview2/" target="_blank" rel="noopener noreferrer">Microsoft WebView2</a> · <a href="https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist" target="_blank" rel="noopener noreferrer">Visual C++ runtime</a></p>}</div>
    <p className="platform-footnote">Windows and Linux packages are early previews. Native UI checks do not replace microphone, keyboard, and insertion testing on physical devices. For older PCs, start with the two-thread CPU setting. Linux single-key shortcuts may also reach the foreground app; modifier combinations are recommended. Smaller downloads and lower RAM are separate goals; no accuracy or speed guarantee is implied.</p>
  </section>;
}
