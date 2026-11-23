export type CanvasColorTheme = "light" | "dark";
export type CanvasBackgroundMode = "dots" | "lines" | "blank";

export const canvasThemes = {
    light: {
        canvas: {
            background: "#f7fcff",
            dot: "rgba(16,36,66,.28)",
            line: "rgba(16,36,66,.12)",
            selectionStroke: "#102442",
            selectionFill: "rgba(28,25,23,.06)",
        },
        node: {
            label: "#47627a",
            fill: "#ddf5ff",
            panel: "#ffffff",
            stroke: "#c8e8f7",
            activeStroke: "#102442",
            placeholder: "#66859b",
            text: "#102442",
            muted: "#66859b",
            faint: "#99bbcc",
        },
        toolbar: {
            panel: "rgba(255,255,255,.96)",
            border: "#c8e8f7",
            item: "#47627a",
            itemHover: "#ddf5ff",
            activeBg: "#ddf5ff",
            activeText: "#102442",
        },
    },
    dark: {
        canvas: {
            background: "#0b1b32",
            dot: "rgba(245,245,244,.24)",
            line: "rgba(245,245,244,.10)",
            selectionStroke: "#fafaf9",
            selectionFill: "rgba(250,250,249,.10)",
        },
        node: {
            label: "#d6d3d1",
            fill: "#102442",
            panel: "#102442",
            stroke: "#294862",
            activeStroke: "#fafaf9",
            placeholder: "#99bbcc",
            text: "#f5f5f4",
            muted: "#d6d3d1",
            faint: "#66859b",
        },
        toolbar: {
            panel: "rgba(31,29,26,.96)",
            border: "#294862",
            item: "#d6d3d1",
            itemHover: "#102442",
            activeBg: "#193758",
            activeText: "#f5f5f4",
        },
    },
} as const;

export type CanvasTheme = (typeof canvasThemes)[CanvasColorTheme];
