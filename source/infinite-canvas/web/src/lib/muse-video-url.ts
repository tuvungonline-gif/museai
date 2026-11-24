import { MUSE_API_BASE } from "@/constant/runtime-config";

const VIDEO_FILE_PATH = /^\/v1\/media\/[a-z\d_-]{1,180}\.(mp4|webm|mov)$/i;
const RELAY_PREFIX = "/employee-api";

export function isMuseRelayBase(value: string): boolean {
    if (typeof window === "undefined" || !value) return false;
    try {
        const base = new URL(value, window.location.origin);
        return base.origin === window.location.origin && /^\/employee-api(?:\/v1)?\/?$/.test(base.pathname);
    } catch {
        return false;
    }
}

export function museVideoRelayPath(value: string): string | undefined {
    if (!isMuseRelayBase(MUSE_API_BASE) || !value) return;

    try {
        const origin = window.location.origin;
        const video = new URL(value, origin);
        if (video.origin === origin && video.pathname.startsWith(RELAY_PREFIX)) {
            return VIDEO_FILE_PATH.test(video.pathname.slice(RELAY_PREFIX.length)) ? video.pathname : undefined;
        }

        const legacyLoopback = video.port === "1314" && ["127.0.0.1", "localhost", "[::1]"].includes(video.hostname);
        if ((video.origin === origin || legacyLoopback) && VIDEO_FILE_PATH.test(video.pathname)) {
            return RELAY_PREFIX + video.pathname;
        }
    } catch {
        return;
    }
}
