import { AppProvider } from "@/contexts/AppContext";
import { AuthProvider } from "@/contexts/AuthContext";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      <AuthProvider>
        <div className="min-h-screen bg-zinc-950 text-zinc-100">{children}</div>
      </AuthProvider>
    </AppProvider>
  );
}
