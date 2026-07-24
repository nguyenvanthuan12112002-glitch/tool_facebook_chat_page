import PageSyncCard from "../components/PageSyncCard";
import ErrorBoundary from "../components/ErrorBoundary";

export default function Home() {
  return (
    <main style={{ 
      width: "100vw",
      height: "100vh",
      overflow: "hidden",
      background: "#0f172a" 
    }}>
      <ErrorBoundary>
        <PageSyncCard />
      </ErrorBoundary>
    </main>
  );
}
