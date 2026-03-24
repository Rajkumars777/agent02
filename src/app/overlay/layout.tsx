import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "Nexus Overlay",
};

export default function OverlayLayout({ children }: { children: React.ReactNode }) {
    return (
        <div style={{ width: "100vw", height: "100vh", background: "transparent", overflow: "hidden" }}>
            {children}
        </div>
    );
}
