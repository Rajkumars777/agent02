"use client";
import { useEffect, useRef } from "react";

interface Props {
  url: string;
  isModalOpen: boolean;
}

export default function BrowserViewport({ url, isModalOpen }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  const updateBounds = async () => {
    // Only run inside Tauri desktop (where window.__TAURI__ exists)
    if (
      typeof window === "undefined" ||
      !(window as any).__TAURI__ ||
      !containerRef.current
    ) {
      return;
    }

    const { invoke } = await import("@tauri-apps/api/core");

    if (isModalOpen) {
      await invoke("hide_browser_view", { visible: false });
      return;
    }

    const rect = containerRef.current.getBoundingClientRect();

    await invoke("mount_browser_view", {
      url,
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
    });

    await invoke("hide_browser_view", { visible: true });
  };

  useEffect(() => {
    updateBounds();

    let timeout: number;
    const handleResize = () => {
      clearTimeout(timeout);
      timeout = window.setTimeout(updateBounds, 50);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      // Hide browser view when unmounting, only in Tauri
      if (typeof window !== "undefined" && (window as any).__TAURI__) {
        import("@tauri-apps/api/core")
          .then(({ invoke }) =>
            invoke("hide_browser_view", { visible: false })
          )
          .catch(() => {
            // Ignore cleanup errors in web mode
          });
      }
    };
  }, [url, isModalOpen]);

  return (
    <div className="flex flex-col w-full h-full">
      <div
        ref={containerRef}
        className="flex-1 bg-gray-900 rounded-lg border border-gray-700 w-full h-full"
      />
    </div>
  );
}
