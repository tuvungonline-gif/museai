import { FileText, ImagePlus, Images, Maximize2, Settings2, Video } from "lucide-react";

import { CAN_MANAGE_SETTINGS } from "./runtime-config";

const allNavigationTools = [
    {
        slug: "canvas",
        icon: Maximize2,
    },
    {
        slug: "image",
        icon: ImagePlus,
    },
    {
        slug: "video",
        icon: Video,
    },
    {
        slug: "prompts",
        icon: FileText,
    },
    {
        slug: "assets",
        icon: Images,
    },
    {
        slug: "config",
        icon: Settings2,
    },
] as const;

export type NavigationToolSlug = (typeof allNavigationTools)[number]["slug"];

export const navigationTools = allNavigationTools.filter((tool) => tool.slug !== "config" || CAN_MANAGE_SETTINGS);
