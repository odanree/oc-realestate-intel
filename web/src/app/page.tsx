import Chat from "./components/Chat";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-6 py-3">
        <div className="max-w-6xl mx-auto flex items-baseline justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              oc-realestate-intel
            </h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Multi-agent LangGraph over Orange County parcels
            </p>
          </div>
          <a
            href="https://github.com/odanree/oc-realestate-intel"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
          >
            github →
          </a>
        </div>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-6">
        <Chat />
      </main>
    </div>
  );
}
