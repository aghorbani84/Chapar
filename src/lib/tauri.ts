// Wrapper to allow running the app in a web browser for demo purposes
const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

export async function invoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
    if (isTauri) {
        // Dynamically import actual Tauri API only when running in the desktop app
        const { invoke: tauriInvoke } = await import('@tauri-apps/api/core');
        return tauriInvoke<T>(command, args);
    }

    console.warn(`[Web Demo Mode] Mocking Rust command: ${command}`);
    
    // Mock responses for web demo
    if (command === 'execute_request') {
        return {
            status: 200,
            latency: Math.floor(Math.random() * 100) + 50,
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ message: "This is a mocked response for the web demo. Download the desktop app for real requests." })
        } as T;
    }

    if (command === 'get_collections') {
        return [{ id: 1, name: 'Demo Collection' }] as T;
    }

    return {} as T;
}
