import Sidebar from "@/components/Sidebar";
import { AnalyzeProvider } from "@/contexts/AnalyzeContext";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AnalyzeProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 p-8 bg-neutral-900 text-neutral-100">
          {children}
        </main>
      </div>
    </AnalyzeProvider>
  );
}
