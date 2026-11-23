import { ArrowUpRight, ImagePlus, Video } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

const tools = [
    {
        id: "video",
        Icon: Video,
        iconClass: "bg-primary text-primary-foreground",
        hoverClass: "hover:border-blue-400 dark:hover:border-blue-300",
    },
    {
        id: "image",
        Icon: ImagePlus,
        iconClass: "bg-[#FDA003] text-[#102442]",
        hoverClass: "hover:border-amber-500 dark:hover:border-amber-300",
    },
] as const;

export default function IndexPage() {
    const { t } = useTranslation();

    return (
        <main className="h-full overflow-y-auto bg-background bg-[radial-gradient(ellipse_at_top,var(--muted),transparent_65%)] text-foreground">
            <section aria-labelledby="home-title" className="mx-auto flex min-h-full w-full max-w-5xl flex-col justify-center gap-7 px-4 py-8 sm:gap-10 sm:px-8 sm:py-14">
                <header className="text-center">
                    <div className="inline-flex items-center gap-2.5 text-left">
                        <img src="/brand/bee-symbol.svg" alt="" width="48" height="48" className="size-12 rounded-xl bg-white p-1" />
                        <div>
                            <p className="text-lg leading-tight font-bold tracking-wide">IBEE</p>
                            <p className="text-xs leading-5 text-muted-foreground">Smart tools. Simple work.</p>
                        </div>
                    </div>
                    <h1 id="home-title" className="mt-5 text-3xl leading-tight font-semibold tracking-tight text-balance sm:mt-6 sm:text-5xl">
                        {t("home.title")}
                    </h1>
                    <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-pretty text-muted-foreground sm:text-base sm:leading-7">
                        {t("home.description")}
                    </p>
                </header>

                <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 sm:gap-5">
                    {tools.map(({ id, Icon, iconClass, hoverClass }) => (
                        <Link
                            key={id}
                            to={`/${id}`}
                            aria-labelledby={`home-${id}-title`}
                            aria-describedby={`home-${id}-description`}
                            className={`group flex min-w-0 flex-col gap-3 rounded-2xl border bg-card p-4 text-card-foreground shadow-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring sm:gap-5 sm:p-6 ${hoverClass}`}
                        >
                            <div className="flex items-center justify-between gap-4">
                                <span className={`grid size-11 shrink-0 place-items-center rounded-xl sm:size-12 ${iconClass}`}>
                                    <Icon aria-hidden="true" className="size-6" />
                                </span>
                                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-muted text-foreground transition-colors group-hover:bg-accent">
                                    <ArrowUpRight aria-hidden="true" className="size-5" />
                                </span>
                            </div>
                            <div>
                                <h2 id={`home-${id}-title`} className="text-xl font-semibold tracking-tight sm:text-2xl">
                                    {t(`home.${id}.title`)}
                                </h2>
                                <p id={`home-${id}-description`} className="mt-1 text-sm leading-6 text-muted-foreground">
                                    {t(`home.${id}.description`)}
                                </p>
                            </div>
                        </Link>
                    ))}
                </div>
            </section>
        </main>
    );
}
