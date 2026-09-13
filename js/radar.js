/* ============================================================
   RADAR INSTITUCIONAL — radar.js
   V2.1

   Fonte única da interface:
       ./radar.json

   Funções:
   - carrega radar.json
   - renderiza todos os blocos
   - controla sidebar
   - exibe somente a página selecionada
   ============================================================ */

"use strict";


/* ============================================================
   CONFIGURAÇÃO
   ============================================================ */

const RADAR_JSON = "./radar.json";

const $ = (id) =>
    document.getElementById(id);


const LABELS = {

    OPEN: "ABERTO",
    CLOSED: "FECHADO",

    NOT_AVAILABLE: "N/D",

    BULLISH: "BULLISH",
    BEARISH: "BEARISH",

    CAUTION: "CAUTION",
    NEUTRAL: "NEUTRAL",
    SELECTIVE: "SELECTIVE",

    MELHORANDO: "MELHORANDO",

    ESTAVEL: "ESTÁVEL",
    ESTÁVEL: "ESTÁVEL",

    ALTO: "ALTO",
    MODERADO: "MODERADO",

    FORTE: "FORTE",

    MEDIA: "MÉDIA",
    CRITICA: "CRÍTICA",

    POSITIVE: "POSITIVO",
    NEGATIVE: "NEGATIVO",

    SAIDA_FORTE: "SAÍDA FORTE",

    HOLD: "HOLD",
    WATCH: "WATCH"

};


/* ============================================================
   HELPERS
   ============================================================ */

function isMissing(value) {

    return (
        value === null ||
        value === undefined ||
        value === ""
    );

}


function text(
    value,
    fallback = "N/D"
) {

    return isMissing(value)
        ? fallback
        : String(value);

}


function label(value) {

    if (isMissing(value)) {

        return "N/D";

    }

    const key =
        String(value)
            .toUpperCase();

    return (
        LABELS[key] ||
        String(value)
    );

}


function numberBR(
    value,
    decimals = 2
) {

    if (
        isMissing(value) ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "N/D";

    }

    return Number(value)
        .toLocaleString(
            "pt-BR",
            {
                minimumFractionDigits:
                    decimals,

                maximumFractionDigits:
                    decimals
            }
        );

}


function integerBR(value) {

    if (
        isMissing(value) ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "N/D";

    }

    return Number(value)
        .toLocaleString(
            "pt-BR",
            {
                maximumFractionDigits: 0
            }
        );

}


function percentBR(
    value,
    decimals = 2
) {

    if (
        isMissing(value) ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "N/D";

    }

    const n =
        Number(value);

    const sign =
        n > 0
            ? "+"
            : "";

    return (
        `${sign}` +
        `${numberBR(n, decimals)}%`
    );

}


function priceUSD(value) {

    if (
        isMissing(value) ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "N/D";

    }

    return (
        `US$ ${numberBR(value, 2)}`
    );

}


function moneyBRL(value) {

    if (
        isMissing(value) ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "N/D";

    }

    const n =
        Number(value);

    const sign =
        n > 0
            ? "+"
            : n < 0
                ? "-"
                : "";

    return (
        `${sign}R$ ` +
        `${numberBR(
            Math.abs(n),
            2
        )} bi`
    );

}


function dateBR(value) {

    if (!value) {

        return "N/D";

    }

    const parts =
        String(value)
            .split("-");

    if (
        parts.length !== 3
    ) {

        return text(value);

    }

    return (
        `${parts[2]}/` +
        `${parts[1]}/` +
        `${parts[0]}`
    );

}


function dateTimeBR(value) {

    if (!value) {

        return "N/D";

    }

    const date =
        new Date(value);

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return text(value);

    }

    return date
        .toLocaleString(
            "pt-BR",
            {
                timeZone:
                    "America/Sao_Paulo",

                day:
                    "2-digit",

                month:
                    "2-digit",

                year:
                    "numeric",

                hour:
                    "2-digit",

                minute:
                    "2-digit"
            }
        );

}


function statusLabel(value) {

    return label(value);

}


function setText(
    id,
    value,
    formatter = text
) {

    const element =
        $(id);

    if (!element) {

        return;

    }

    element.textContent =
        formatter(value);

}


function applyState(
    element,
    value
) {

    if (!element) {

        return;

    }

    element.classList.remove(
        "bullish",
        "bearish",
        "warning",
        "positive"
    );

    const normalized =
        String(
            value ?? ""
        )
            .toUpperCase();


    if (

        normalized.includes(
            "BULLISH"
        ) ||

        normalized.includes(
            "POSITIVE"
        ) ||

        normalized.includes(
            "MELHORANDO"
        )

    ) {

        element.classList.add(
            "bullish"
        );

    } else if (

        normalized.includes(
            "BEARISH"
        ) ||

        normalized.includes(
            "NEGATIVE"
        ) ||

        normalized.includes(
            "RISK_OFF"
        ) ||

        normalized === "ALTO"

    ) {

        element.classList.add(
            "bearish"
        );

    } else if (

        normalized.includes(
            "CAUTION"
        ) ||

        normalized.includes(
            "NEUTRAL"
        ) ||

        normalized.includes(
            "MODERADO"
        ) ||

        normalized.includes(
            "WATCH"
        )

    ) {

        element.classList.add(
            "warning"
        );

    }

}


function setStateText(
    id,
    value
) {

    const element =
        $(id);

    if (!element) {

        return;

    }

    element.textContent =
        label(value);

    applyState(
        element,
        value
    );

}


function clear(element) {

    if (element) {

        element
            .replaceChildren();

    }

}


function td(
    value,
    className = ""
) {

    const element =
        document
            .createElement("td");

    if (className) {

        element.className =
            className;

    }

    element.textContent =
        text(value);

    return element;

}


function strongTd(value) {

    const element =
        document
            .createElement("td");

    const strong =
        document
            .createElement("strong");

    strong.textContent =
        text(value);

    element
        .appendChild(strong);

    return element;

}


function stateTd(value) {

    const element =
        document
            .createElement("td");

    const span =
        document
            .createElement("span");

    span.className =
        "badge";

    span.textContent =
        label(value);

    applyState(
        span,
        value
    );

    element
        .appendChild(span);

    return element;

}


/* ============================================================
   MARKET META
   ============================================================ */

function marketMeta(item) {

    if (!item) {

        return "N/D";

    }

    const parts = [];


    if (
        !isMissing(
            item.change_pct
        )
    ) {

        parts.push(
            percentBR(
                item.change_pct
            )
        );

    }


    if (
        !isMissing(
            item.market_date
        )
    ) {

        parts.push(
            dateBR(
                item.market_date
            )
        );

    }


    if (
        !isMissing(
            item.market_status
        )
    ) {

        parts.push(
            statusLabel(
                item.market_status
            )
        );

    }


    return parts.length

        ? parts.join(" · ")

        : "N/D";

}


/* ============================================================
   HEADER / RESUMO
   ============================================================ */

function renderHeader(data) {

    const radar =
        data.radar || {};

    const brazil =
        data.brazil || {};


    setText(
        "dataAtualizacao",
        radar.generated_at,
        dateTimeBR
    );


    const marketStatus =

        brazil.ibovespa
            ?.market_status ||

        data.global_market
            ?.sp500
            ?.market_status ||

        "NOT_AVAILABLE";


    setText(
        "marketStatus",
        statusLabel(
            marketStatus
        )
    );


    const dot =
        $("marketStatusDot");


    if (dot) {

        dot.classList.remove(
            "positive"
        );


        if (
            marketStatus ===
            "OPEN"
        ) {

            dot.style.background =
                "#22C55E";

        } else if (

            marketStatus ===
            "CLOSED"

        ) {

            dot.style.background =
                "#F59E0B";

        } else {

            dot.style.background =
                "#94A3B8";

        }

    }


    setStateText(
        "marketRegime",
        radar.market_regime
    );


    setStateText(
        "institutionalSentiment",
        radar.institutional_sentiment
    );


    setStateText(
        "dailyBias",
        radar.daily_bias
    );


    setStateText(
        "riskLevel",
        radar.risk_level
    );


    setText(
        "radarSummary",
        radar.summary
    );


    setStateText(
        "riskBadge",
        radar.risk_level
    );


    setStateText(
        "overviewBadge",
        radar.market_regime
    );

}


/* ============================================================
   MARKET OVERVIEW
   ============================================================ */

function renderMarketCard(
    id,
    item,
    formatter = numberBR
) {

    setText(
        id,
        item?.value,
        formatter
    );


    setText(
        `${id}Meta`,

        item
            ? marketMeta(item)
            : "N/D"
    );


    const valueElement =
        $(id);


    if (

        valueElement &&

        !isMissing(
            item?.change_pct
        )

    ) {

        applyState(

            valueElement,

            Number(
                item.change_pct
            ) >= 0

                ? "POSITIVE"

                : "NEGATIVE"

        );

    }

}


function renderMarketOverview(data) {

    const global =
        data.global_market || {};

    const brazil =
        data.brazil || {};


    renderMarketCard(
        "ibovespa",
        brazil.ibovespa,
        integerBR
    );


    renderMarketCard(
        "dolar",
        brazil.dollar_brl,
        (v) =>
            numberBR(v, 2)
    );


    renderMarketCard(
        "sp500",
        global.sp500
    );


    renderMarketCard(
        "nasdaq",
        global.nasdaq
    );


    renderMarketCard(
        "brent",
        global.brent
    );


    renderMarketCard(
        "treasury10y",
        global.treasury_10y,
        (v) =>
            `${numberBR(v, 2)}%`
    );


    renderMarketCard(
        "dow",
        global.dow
    );


    renderMarketCard(
        "russell2000",
        global.russell2000
    );


    renderMarketCard(
        "wti",
        global.wti
    );


    renderMarketCard(
        "vix",
        global.vix
    );


    renderMarketCard(
        "treasury2y",
        global.treasury_2y,
        (v) =>
            `${numberBR(v, 2)}%`
    );


    renderMarketCard(
        "dollarIndex",
        global.dollar_index
    );

}


/* ============================================================
   MACRO
   ============================================================ */

function macroNumber(
    value,
    eventName = ""
) {

    if (
        isMissing(value)
    ) {

        return "N/D";

    }


    const name =
        String(eventName)
            .toLowerCase();


    if (

        name.includes(
            "unemployment"
        ) ||

        name.includes(
            "cpi"
        ) ||

        name.includes(
            "ppi"
        ) ||

        name.includes(
            "inflation"
        )

    ) {

        return (
            `${numberBR(
                value,
                2
            )}%`
        );

    }


    if (

        typeof value ===
            "number" &&

        Number.isInteger(
            value
        )

    ) {

        return integerBR(
            value
        );

    }


    return numberBR(
        value,
        2
    );

}


function macroDate(item) {

    const start =
        dateBR(
            item.start_date
        );


    const end =
        item.end_date

            ? ` – ${dateBR(
                item.end_date
            )}`

            : "";


    const time =
        item.time

            ? ` · ${item.time}`

            : "";


    return (
        `${start}` +
        `${end}` +
        `${time}`
    );

}


function renderMacro(data) {

    const tbody =
        $("macroTable");


    clear(tbody);


    (data.macro || [])
        .forEach(
            (item) => {

                const row =
                    document
                        .createElement(
                            "tr"
                        );


                row.appendChild(
                    strongTd(
                        item.event
                    )
                );


                row.appendChild(
                    td(
                        macroDate(
                            item
                        )
                    )
                );


                row.appendChild(
                    td(
                        macroNumber(
                            item.result,
                            item.event
                        )
                    )
                );


                row.appendChild(
                    td(
                        macroNumber(
                            item.expectation,
                            item.event
                        )
                    )
                );


                row.appendChild(
                    stateTd(
                        item.impact ||
                        item.magnitude
                    )
                );


                row.appendChild(
                    stateTd(
                        item.win_impact
                    )
                );


                row.appendChild(
                    stateTd(
                        item.wdo_impact
                    )
                );


                row.appendChild(
                    td(
                        item.comment
                    )
                );


                tbody
                    ?.appendChild(
                        row
                    );

            }
        );

}


/* ============================================================
   BRASIL / FLUXO ESTRANGEIRO
   ============================================================ */

function renderBrazil(data) {

    const brazil =
        data.brazil || {};

    const flow =
        data.foreign_flow || {};


    setStateText(
        "brazilBias",
        brazil.market_bias
    );


    renderMarketCard(
        "brazilIbovespa",
        brazil.ibovespa,
        integerBR
    );


    renderMarketCard(
        "ibovespaFutures",
        brazil.ibovespa_futures,
        integerBR
    );


    renderMarketCard(
        "brazilDollar",
        brazil.dollar_brl,
        (v) =>
            numberBR(v, 2)
    );


    setText(
        "selic",
        brazil.selic,
        (v) =>

            isMissing(v)

                ? "N/D"

                : `${numberBR(
                    v,
                    2
                )}%`
    );


    setText(
        "ipca",
        brazil.ipca,
        (v) =>

            isMissing(v)

                ? "N/D"

                : `${numberBR(
                    v,
                    2
                )}%`
    );


    setText(
        "gdp",
        brazil.gdp,
        (v) =>

            isMissing(v)

                ? "N/D"

                : `${numberBR(
                    v,
                    2
                )}%`
    );


    setStateText(
        "fiscalRisk",
        brazil.fiscal_risk
    );


    setStateText(
        "politicalRisk",
        brazil.political_risk
    );


    setText(
        "brazilComment",
        brazil.comment
    );


    setStateText(
        "foreignFlowStatus",
        flow.status
    );


    setText(
        "foreignFlowDaily",
        moneyBRL(
            flow.daily_flow_brl
        )
    );


    setText(
        "foreignFlowMonthly",
        moneyBRL(
            flow.monthly_flow_brl
        )
    );


    setText(
        "foreignFlowYtd",
        moneyBRL(
            flow.year_to_date_flow_brl
        )
    );


    setStateText(
        "foreignFlowTrend",
        flow.trend
    );


    setText(
        "foreignFlowDelay",
        flow.data_delay
    );


    setStateText(
        "foreignFlowTrendBadge",
        flow.trend
    );


    setText(
        "foreignFlowComment",
        flow.comment
    );

}


/* ============================================================
   WIN / WDO / DI
   ============================================================ */

function conditionText(value) {

    if (
        isMissing(value)
    ) {

        return "N/D";

    }


    if (
        value === true
    ) {

        return "SIM";

    }


    if (
        value === false
    ) {

        return "NÃO";

    }


    return label(value);

}


function addCondition(
    list,
    title,
    value
) {

    if (!list) {

        return;

    }


    const li =
        document
            .createElement(
                "li"
            );


    li.textContent =
        `${title}: ` +
        `${conditionText(value)}`;


    list
        .appendChild(li);

}


function renderFutures(data) {

    const futures =
        data.futures || {};

    const win =
        futures.win || {};

    const wdo =
        futures.wdo || {};

    const di =
        futures.di || {};

    const conditions =
        futures.conditions || {};


    setStateText(
        "winBias",
        win.bias
    );


    setStateText(
        "wdoBias",
        wdo.bias
    );


    setStateText(
        "diBias",
        di.bias
    );


    setText(
        "winBuyConfidence",

        isMissing(
            win.buy_confidence
        )

            ? "N/D"

            : `${numberBR(
                win.buy_confidence,
                1
            )} / 10`
    );


    setText(
        "winSellConfidence",

        isMissing(
            win.sell_confidence
        )

            ? "N/D"

            : `${numberBR(
                win.sell_confidence,
                1
            )} / 10`
    );


    const winList =
        $("winConditionsList");


    const wdoList =
        $("wdoDiConditionsList");


    clear(winList);

    clear(wdoList);


    addCondition(
        winList,
        "WIN acima da VWAP",
        conditions
            .win_above_vwap
    );


    addCondition(
        winList,
        "Volume comprador",
        conditions
            .buy_volume
    );


    addCondition(
        wdoList,
        "WDO abaixo da VWAP",
        conditions
            .wdo_below_vwap
    );


    addCondition(
        wdoList,
        "DI perdendo força",
        conditions
            .di_losing_strength
    );


    const tbody =
        $("futuresConditionsTable");


    clear(tbody);


    const rows = [

        [
            "WIN acima da VWAP",
            conditions.win_above_vwap,
            "—",
            "—"
        ],

        [
            "WDO abaixo da VWAP",
            "—",
            conditions.wdo_below_vwap,
            "—"
        ],

        [
            "DI perdendo força",
            "—",
            "—",
            conditions.di_losing_strength
        ],

        [
            "Volume comprador",
            conditions.buy_volume,
            "—",
            "—"
        ]

    ];


    rows.forEach(
        (item) => {

            const row =
                document
                    .createElement(
                        "tr"
                    );


            row.appendChild(
                td(
                    item[0]
                )
            );


            row.appendChild(
                td(
                    conditionText(
                        item[1]
                    )
                )
            );


            row.appendChild(
                td(
                    conditionText(
                        item[2]
                    )
                )
            );


            row.appendChild(
                td(
                    conditionText(
                        item[3]
                    )
                )
            );


            tbody
                ?.appendChild(
                    row
                );

        }
    );

}


/* ============================================================
   CARDS
   ============================================================ */

function makeCard(
    title,
    subtitle,
    rows = []
) {

    const card =
        document
            .createElement(
                "div"
            );


    card.className =
        "ranking-card";


    const rank =
        document
            .createElement(
                "div"
            );


    rank.className =
        "rank";


    rank.textContent =
        title;


    const ticker =
        document
            .createElement(
                "div"
            );


    ticker.className =
        "ticker";


    ticker.textContent =
        subtitle;


    card.appendChild(
        rank
    );


    card.appendChild(
        ticker
    );


    rows.forEach(
        (item) => {

            const line =
                document
                    .createElement(
                        "div"
                    );


            line.className =
                "strategy";


            if (
                typeof item ===
                "string"
            ) {

                line.textContent =
                    item;

            } else {

                const strong =
                    document
                        .createElement(
                            "strong"
                        );


                strong.textContent =
                    `${item.label}: `;


                line.appendChild(
                    strong
                );


                line.appendChild(
                    document
                        .createTextNode(
                            text(
                                item.value
                            )
                        )
                );

            }


            card.appendChild(
                line
            );

        }
    );


    return card;

}


/* ============================================================
   SETORES
   ============================================================ */

function renderSectors(data) {

    const grid =
        $("sectorsGrid");


    clear(grid);


    (data.sectors || [])
        .forEach(
            (
                item,
                index
            ) => {

                const card =
                    makeCard(

                        `#${index + 1}`,

                        item.sector,

                        [

                            {
                                label:
                                    "Performance",

                                value:
                                    percentBR(
                                        item.performance_pct
                                    )
                            },

                            {
                                label:
                                    "Tendência",

                                value:
                                    label(
                                        item.trend
                                    )
                            },

                            {
                                label:
                                    "Viés",

                                value:
                                    label(
                                        item.bias
                                    )
                            },

                            item.comment

                        ]

                    );


                grid
                    ?.appendChild(
                        card
                    );

            }
        );

}


/* ============================================================
   POWER / DATA CENTER
   ============================================================ */

function renderPower(data) {

    const grid =
        $("powerGrid");


    clear(grid);


    (data.power_data_center || [])
        .forEach(
            (
                item,
                index
            ) => {

                const card =
                    makeCard(

                        `#${index + 1}`,

                        item.ticker,

                        [

                            {
                                label:
                                    "Empresa",

                                value:
                                    item.company
                            },

                            {
                                label:
                                    "Preço",

                                value:
                                    priceUSD(
                                        item.price
                                    )
                            },

                            {
                                label:
                                    "Variação",

                                value:
                                    percentBR(
                                        item.change_pct
                                    )
                            },

                            {
                                label:
                                    "Tendência",

                                value:
                                    label(
                                        item.trend
                                    )
                            },

                            {
                                label:
                                    "Viés institucional",

                                value:
                                    label(
                                        item.institutional_bias
                                    )
                            },

                            {
                                label:
                                    "Recomendação",

                                value:
                                    label(
                                        item.recommendation
                                    )
                            },

                            item.comment

                        ]

                    );


                grid
                    ?.appendChild(
                        card
                    );

            }
        );

}


/* ============================================================
   NUCLEAR
   ============================================================ */

function renderNuclear(data) {

    const grid =
        $("nuclearGrid");


    clear(grid);


    (data.nuclear || [])
        .forEach(
            (
                item,
                index
            ) => {

                const card =
                    makeCard(

                        `#${index + 1}`,

                        item.ticker,

                        [

                            {
                                label:
                                    "Empresa",

                                value:
                                    item.company
                            },

                            {
                                label:
                                    "Preço",

                                value:
                                    priceUSD(
                                        item.price
                                    )
                            },

                            {
                                label:
                                    "Variação",

                                value:
                                    percentBR(
                                        item.change_pct
                                    )
                            },

                            {
                                label:
                                    "Tendência",

                                value:
                                    label(
                                        item.trend
                                    )
                            },

                            {
                                label:
                                    "Catalisador",

                                value:
                                    item.catalyst
                            },

                            {
                                label:
                                    "Recomendação",

                                value:
                                    label(
                                        item.recommendation
                                    )
                            },

                            item.comment

                        ]

                    );


                grid
                    ?.appendChild(
                        card
                    );

            }
        );

}


/* ============================================================
   PENNY STOCKS
   ============================================================ */

function renderPenny(data) {

    const grid =
        $("pennyGrid");


    clear(grid);


    (data.penny_stocks || [])
        .forEach(
            (
                item,
                index
            ) => {

                const card =
                    makeCard(

                        `#${index + 1}`,

                        item.ticker,

                        [

                            {
                                label:
                                    "Empresa",

                                value:
                                    item.company
                            },

                            {
                                label:
                                    "Preço",

                                value:
                                    priceUSD(
                                        item.price
                                    )
                            },

                            {
                                label:
                                    "Variação",

                                value:
                                    percentBR(
                                        item.change_pct
                                    )
                            },

                            {
                                label:
                                    "Volume",

                                value:
                                    integerBR(
                                        item.volume
                                    )
                            },

                            {
                                label:
                                    "Risco",

                                value:
                                    label(
                                        item.risk_level
                                    )
                            },

                            {
                                label:
                                    "Catalisador",

                                value:
                                    item.catalyst
                            },

                            {
                                label:
                                    "Recomendação",

                                value:
                                    label(
                                        item.recommendation
                                    )
                            },

                            item.comment

                        ]

                    );


                grid
                    ?.appendChild(
                        card
                    );

            }
        );

}


/* ============================================================
   SWING TRADES
   ============================================================ */

function renderSwing(data) {

    const tbody =
        $("swingTable");


    const details =
        $("swingDetails");


    clear(tbody);

    clear(details);


    (data.swing_trades || [])
        .forEach(
            (
                item,
                index
            ) => {

                const row =
                    document
                        .createElement(
                            "tr"
                        );


                row.appendChild(
                    strongTd(
                        item.ticker
                    )
                );


                row.appendChild(
                    td(
                        priceUSD(
                            item.price
                        )
                    )
                );


                row.appendChild(
                    td(
                        priceUSD(
                            item.entry
                        )
                    )
                );


                row.appendChild(
                    td(
                        priceUSD(
                            item.stop
                        )
                    )
                );


                row.appendChild(
                    td(
                        priceUSD(
                            item.target
                        )
                    )
                );


                row.appendChild(
                    td(

                        isMissing(
                            item.risk_reward
                        )

                            ? "N/D"

                            : numberBR(
                                item.risk_reward,
                                2
                            )

                    )
                );


                row.appendChild(
                    stateTd(
                        item.technical_bias
                    )
                );


                row.appendChild(
                    stateTd(
                        item.recommendation
                    )
                );


                tbody
                    ?.appendChild(
                        row
                    );


                const catalysts =

                    Array.isArray(
                        item.catalysts
                    )

                        ? item.catalysts
                            .join(
                                " · "
                            )

                        : text(
                            item.catalysts
                        );


                details
                    ?.appendChild(

                        makeCard(

                            `#${index + 1}`,

                            `${item.ticker} · ${item.company}`,

                            [

                                {
                                    label:
                                        "Tese",

                                    value:
                                        item.thesis
                                },

                                {
                                    label:
                                        "Catalisadores",

                                    value:
                                        catalysts
                                }

                            ]

                        )

                    );

            }
        );

}


/* ============================================================
   CARTEIRA
   ============================================================ */

function renderPortfolio(data) {

    const tbody =
        $("portfolioTable");


    const details =
        $("portfolioDetails");


    clear(tbody);

    clear(details);


    (data.portfolio || [])
        .forEach(
            (
                item,
                index
            ) => {

                const row =
                    document
                        .createElement(
                            "tr"
                        );


                row.appendChild(
                    strongTd(
                        item.ticker
                    )
                );


                row.appendChild(
                    td(
                        priceUSD(
                            item.price
                        )
                    )
                );


                row.appendChild(
                    td(
                        percentBR(
                            item.change_pct
                        )
                    )
                );


                row.appendChild(
                    stateTd(
                        item.position_bias
                    )
                );


                row.appendChild(
                    stateTd(
                        item.risk_level
                    )
                );


                row.appendChild(
                    stateTd(
                        item.recommendation
                    )
                );


                tbody
                    ?.appendChild(
                        row
                    );


                const catalysts =

                    Array.isArray(
                        item.catalysts
                    )

                        ? item.catalysts
                            .join(
                                " · "
                            )

                        : text(
                            item.catalysts
                        );


                details
                    ?.appendChild(

                        makeCard(

                            `#${index + 1}`,

                            `${item.ticker} · ${item.company}`,

                            [

                                {
                                    label:
                                        "Tese",

                                    value:
                                        item.thesis
                                },

                                {
                                    label:
                                        "Catalisadores",

                                    value:
                                        catalysts
                                }

                            ]

                        )

                    );

            }
        );

}


/* ============================================================
   RANKING INSTITUCIONAL
   ============================================================ */

function renderRanking(data) {

    const tbody =
        $("rankingTable");


    clear(tbody);


    (data.ranking || [])
        .forEach(
            (item) => {

                const row =
                    document
                        .createElement(
                            "tr"
                        );


                row.appendChild(
                    strongTd(
                        `#${item.rank}`
                    )
                );


                row.appendChild(
                    strongTd(
                        item.ticker
                    )
                );


                row.appendChild(
                    td(
                        item.company
                    )
                );


                row.appendChild(
                    strongTd(

                        isMissing(
                            item.score
                        )

                            ? "N/D"

                            : `${numberBR(
                                item.score,
                                1
                            )} / 10`

                    )
                );


                row.appendChild(
                    stateTd(
                        item.recommendation
                    )
                );


                row.appendChild(
                    stateTd(
                        item.risk_level
                    )
                );


                row.appendChild(
                    td(
                        item.reason
                    )
                );


                tbody
                    ?.appendChild(
                        row
                    );

            }
        );

}


/* ============================================================
   ANÁLISE FUNDAMENTALISTA
   ============================================================ */

function renderFundamental(data) {

    const tbody =
        $("fundamentalTable");


    clear(tbody);


    (data.fundamental_analysis || [])
        .forEach(
            (item) => {

                const row =
                    document
                        .createElement(
                            "tr"
                        );


                row.appendChild(
                    strongTd(
                        item.ticker
                    )
                );


                row.appendChild(
                    td(
                        item.valuation
                    )
                );


                row.appendChild(
                    td(

                        isMissing(
                            item.revenue_growth
                        )

                            ? "N/D"

                            : `${numberBR(
                                item.revenue_growth,
                                1
                            )}%`

                    )
                );


                row.appendChild(
                    td(

                        isMissing(
                            item.earnings_growth
                        )

                            ? "N/D"

                            : `${numberBR(
                                item.earnings_growth,
                                1
                            )}%`

                    )
                );


                row.appendChild(
                    td(
                        item.profitability
                    )
                );


                row.appendChild(
                    td(
                        item.balance_sheet
                    )
                );


                row.appendChild(
                    stateTd(
                        item.fundamental_bias
                    )
                );


                tbody
                    ?.appendChild(
                        row
                    );

            }
        );

}


/* ============================================================
   ANÁLISE TÉCNICA
   ============================================================ */

function renderTechnical(data) {

    const tbody =
        $("technicalTable");


    clear(tbody);


    (data.technical_analysis || [])
        .forEach(
            (item) => {

                const row =
                    document
                        .createElement(
                            "tr"
                        );


                row.appendChild(
                    strongTd(
                        item.ticker
                    )
                );


                row.appendChild(
                    stateTd(
                        item.trend
                    )
                );


                row.appendChild(
                    td(
                        priceUSD(
                            item.support
                        )
                    )
                );


                row.appendChild(
                    td(
                        priceUSD(
                            item.resistance
                        )
                    )
                );


                row.appendChild(
                    td(

                        isMissing(
                            item.rsi
                        )

                            ? "N/D"

                            : numberBR(
                                item.rsi,
                                1
                            )

                    )
                );


                row.appendChild(
                    td(

                        isMissing(
                            item.moving_average_20
                        )

                            ? "N/D"

                            : priceUSD(
                                item.moving_average_20
                            )

                    )
                );


                row.appendChild(
                    td(

                        isMissing(
                            item.moving_average_50
                        )

                            ? "N/D"

                            : priceUSD(
                                item.moving_average_50
                            )

                    )
                );


                row.appendChild(
                    td(

                        isMissing(
                            item.moving_average_200
                        )

                            ? "N/D"

                            : priceUSD(
                                item.moving_average_200
                            )

                    )
                );


                row.appendChild(
                    stateTd(
                        item.technical_bias
                    )
                );


                tbody
                    ?.appendChild(
                        row
                    );

            }
        );

}


/* ============================================================
   CATALISADORES
   ============================================================ */

function renderCatalysts(data) {

    const tbody =
        $("catalystsTable");


    clear(tbody);


    (data.catalysts || [])
        .forEach(
            (item) => {

                const row =
                    document
                        .createElement(
                            "tr"
                        );


                row.appendChild(
                    td(
                        dateBR(
                            item.date
                        )
                    )
                );


                row.appendChild(
                    td(
                        item.ticker ||
                        "—"
                    )
                );


                row.appendChild(
                    strongTd(
                        item.event
                    )
                );


                row.appendChild(
                    stateTd(
                        item.importance
                    )
                );


                row.appendChild(
                    td(
                        item.expected_impact
                    )
                );


                row.appendChild(
                    td(
                        item.comment
                    )
                );


                tbody
                    ?.appendChild(
                        row
                    );

            }
        );

}


/* ============================================================
   ALERTAS
   ============================================================ */

function renderAlerts(data) {

    const grid =
        $("alertsList");


    clear(grid);


    (data.alerts || [])
        .forEach(
            (
                item,
                index
            ) => {

                const title =

                    item.ticker

                        ? `${item.type} · ${item.ticker}`

                        : item.type;


                grid
                    ?.appendChild(

                        makeCard(

                            `#${index + 1}`,

                            title,

                            [

                                {
                                    label:
                                        "Severidade",

                                    value:
                                        label(
                                            item.severity
                                        )
                                },

                                {
                                    label:
                                        "Mensagem",

                                    value:
                                        item.message
                                },

                                {
                                    label:
                                        "Ação",

                                    value:
                                        item.action
                                }

                            ]

                        )

                    );

            }
        );

}


/* ============================================================
   CONCLUSÃO OPERACIONAL
   ============================================================ */

function renderConclusion(data) {

    const container =
        $("conclusionText");

    if (!container) {
        return;
    }

    clear(container);

    const conclusion =
        data.operational_conclusion || {};

    const win =
        conclusion.win || {};

    const wdo =
        conclusion.wdo || {};

    const stocks =
        conclusion.stocks || {};


    function addConclusionLine(
        title,
        value
    ) {

        const p =
            document.createElement("p");

        const strong =
            document.createElement("strong");

        strong.textContent =
            `${title}: `;

        p.appendChild(strong);

        p.appendChild(
            document.createTextNode(
                text(value)
            )
        );

        container.appendChild(p);
    }


    addConclusionLine(
        "WIN",
        `${label(win.bias)} — ${text(win.comment)}`
    );

    addConclusionLine(
        "WDO",
        `${label(wdo.bias)} — ${text(wdo.comment)}`
    );

    addConclusionLine(
        "Ações",
        `${label(stocks.bias)} — ${text(stocks.comment)}`
    );

    addConclusionLine(
        "Tema preferido",
        conclusion.preferred_theme
    );

    addConclusionLine(
        "Principal risco",
        conclusion.main_risk
    );

    addConclusionLine(
        "Principal catalisador",
        conclusion.main_catalyst
    );

    addConclusionLine(
        "Ação recomendada",
        conclusion.action
    );

}


/* ============================================================
   FONTES
   ============================================================ */

function renderSources(data) {

    const tbody =
        $("sourcesTable");


    clear(tbody);


    (data.sources || [])
        .forEach(
            (item) => {

                const row =
                    document
                        .createElement(
                            "tr"
                        );


                row.appendChild(
                    strongTd(
                        item.name
                    )
                );


                row.appendChild(
                    td(
                        item.supports
                    )
                );


                row.appendChild(
                    td(
                        dateTimeBR(
                            item.retrieved_at
                        )
                    )
                );


                tbody
                    ?.appendChild(
                        row
                    );

            }
        );

}


/* ============================================================
   CARREGAMENTO DO RADAR.JSON
   ============================================================ */

async function carregarRadar() {

    try {

        const response =
            await fetch(

                RADAR_JSON,

                {
                    cache:
                        "no-store"
                }

            );


        if (
            !response.ok
        ) {

            throw new Error(

                `HTTP ${response.status} ` +
                `ao carregar ${RADAR_JSON}`

            );

        }


        const data =
            await response.json();


        if (
            data.schema_version !==
            "2.1"
        ) {

            console.warn(

                "Schema diferente " +
                "do esperado:",

                data.schema_version

            );

        }


        /* HEADER */

        renderHeader(
            data
        );


        /* OVERVIEW */

        renderMarketOverview(
            data
        );


        /* MACRO */

        renderMacro(
            data
        );


        /* BRASIL */

        renderBrazil(
            data
        );


        /* WIN / WDO / DI */

        renderFutures(
            data
        );


        /* SETORES */

        renderSectors(
            data
        );


        /* POWER */

        renderPower(
            data
        );


        /* NUCLEAR */

        renderNuclear(
            data
        );


        /* SWING */

        renderSwing(
            data
        );


        /* CARTEIRA */

        renderPortfolio(
            data
        );


        /* PENNY STOCKS */

        renderPenny(
            data
        );


        /* RANKING */

        renderRanking(
            data
        );


        /* FUNDAMENTAL */

        renderFundamental(
            data
        );


        /* TÉCNICA */

        renderTechnical(
            data
        );


        /* CATALISADORES */

        renderCatalysts(
            data
        );


        /* ALERTAS */

        renderAlerts(
            data
        );


        /* CONCLUSÃO */

        renderConclusion(
            data
        );


        /* FONTES */

        renderSources(
            data
        );


        console.info(

            "Radar Institucional " +
            "V2.1 carregado " +
            "com sucesso."

        );


    } catch (error) {


        console.error(

            "Erro ao carregar " +
            "Radar Institucional:",

            error

        );


        const summary =
            $("radarSummary");


        if (summary) {

            summary.textContent =

                "Não foi possível " +
                "carregar o radar.json. " +

                "Verifique se o arquivo " +
                "está na raiz do projeto " +

                "e se a página foi aberta " +
                "por um servidor local.";

        }

    }

}


/* ============================================================
   NAVEGAÇÃO ENTRE PÁGINAS
   V3.1 — robusta por ID
   ============================================================ */

const PAGE_TITLES = {
    overview: "Overview",
    macro: "Macro",
    brazil: "Brasil",
    winwdo: "WIN / WDO / DI",
    sectors: "Setores",
    power: "Power / Data Center",
    nuclear: "Nuclear",
    swing: "Swing Trades",
    portfolio: "Carteira",
    penny: "Penny Stocks",
    ranking: "Ranking",
    analysis: "Análises",
    catalysts: "Catalisadores",
    alerts: "Alertas",
    conclusion: "Conclusão"
};


/*
   Lista oficial das 15 páginas.

   Usamos os IDs reais do HTML:
   #overview
   #macro
   #brazil
   etc.

   Isso evita depender de class="radar-page"
   ou data-page.
*/

const PAGE_IDS =
    Object.keys(
        PAGE_TITLES
    );


/* ============================================================
   MOSTRAR UMA ÚNICA PÁGINA
   ============================================================ */

function showPage(
    pageId,
    updateHash = true
) {

    /*
       Se alguém passar um ID inválido,
       voltamos automaticamente para Overview.
    */

    const activeId =
        PAGE_IDS.includes(
            pageId
        )
            ? pageId
            : "overview";


    /* ========================================================
       ESCONDER TODAS AS 15 SEÇÕES
       ======================================================== */

    PAGE_IDS.forEach(
        (id) => {

            const page =
                document.getElementById(
                    id
                );


            /*
               Se alguma seção não existir,
               apenas ignoramos.
            */

            if (!page) {

                return;

            }


            const isActive =
                id === activeId;


            /*
               hidden é a propriedade HTML
               padrão para ocultar elementos.
            */

            page.hidden =
                !isActive;


            /*
               Também aplicamos display diretamente.

               Isso evita qualquer regra do CSS antigo
               sobrescrever o atributo hidden.
            */

            page.style.display =
                isActive
                    ? ""
                    : "none";


            /*
               Mantemos a classe is-active
               para uso visual futuro.
            */

            page.classList.toggle(
                "is-active",
                isActive
            );


            /*
               Acessibilidade.
            */

            page.setAttribute(
                "aria-hidden",
                isActive
                    ? "false"
                    : "true"
            );

        }
    );


    /* ========================================================
       SIDEBAR
       ======================================================== */

    const links =
        document.querySelectorAll(
            ".sidebar-link[data-page-target]"
        );


    links.forEach(
        (link) => {

            const isActive =
                link.dataset.pageTarget ===
                activeId;


            /*
               Destaque azul do item selecionado.
            */

            link.classList.toggle(
                "is-active",
                isActive
            );


            /*
               Acessibilidade.
            */

            if (isActive) {

                link.setAttribute(
                    "aria-current",
                    "page"
                );

            } else {

                link.removeAttribute(
                    "aria-current"
                );

            }

        }
    );


    /* ========================================================
       RESUMO EXECUTIVO
       ======================================================== */

    /*
       radar-summary fica visível somente
       quando Overview estiver selecionado.
    */

    const summary =
        document.getElementById(
            "radar-summary"
        );


    if (summary) {

        const showSummary =
            activeId ===
            "overview";


        summary.hidden =
            !showSummary;


        summary.style.display =
            showSummary
                ? ""
                : "none";

    }


    /* ========================================================
       FONTES
       ======================================================== */

    /*
       O bloco Sources não é uma das 15 páginas.

       Por enquanto ele permanece oculto.
       Depois podemos criar um item "Fontes"
       na sidebar se desejar.
    */

    const sources =
        document.getElementById(
            "sources"
        );


    if (sources) {

        sources.hidden =
            true;

        sources.style.display =
            "none";

    }


    /* ========================================================
       TÍTULO SUPERIOR
       ======================================================== */

    const title =
        document.querySelector(
            ".page-context-title"
        );


    if (title) {

        title.textContent =
            PAGE_TITLES[
                activeId
            ];

    }


    /* ========================================================
       TÍTULO DA ABA DO NAVEGADOR
       ======================================================== */

    document.title =
        `${PAGE_TITLES[activeId]} · Radar Institucional`;


    /* ========================================================
       URL
       ======================================================== */

    /*
       Exemplo:

       Overview:
       http://localhost:8000/#overview

       Setores:
       http://localhost:8000/#sectors

       Power:
       http://localhost:8000/#power
    */

    if (
        updateHash &&
        window.location.hash !==
            `#${activeId}`
    ) {

        history.pushState(

            {
                page:
                    activeId
            },

            "",

            `#${activeId}`

        );

    }


    /* ========================================================
       VOLTAR PARA O TOPO
       ======================================================== */

    window.scrollTo({

        top: 0,

        behavior:
            "auto"

    });

}

/* ============================================================
   ÍCONES DA SIDEBAR NOS TÍTULOS DAS PÁGINAS
   ============================================================ */

function syncPageTitleIcons() {

    PAGE_IDS.forEach((pageId) => {

        const page =
            document.getElementById(pageId);

        if (!page) return;

        const iconTarget =
            page.querySelector(
                ".section-page-icon"
            );

        if (!iconTarget) return;

        const sidebarLink =
            document.querySelector(
                `.sidebar-link[data-page-target="${pageId}"]`
            );

        if (!sidebarLink) return;

        const sidebarSvg =
            sidebarLink.querySelector("svg");

        if (!sidebarSvg) return;

        /*
           Clonamos o SVG para manter apenas uma fonte
           visual dos ícones: a própria sidebar.
        */
        iconTarget.replaceChildren(
            sidebarSvg.cloneNode(true)
        );

    });

}

/* ============================================================
   INICIALIZAR NAVEGAÇÃO
   ============================================================ */

function initPageNavigation() {


    const links =
        document.querySelectorAll(
            ".sidebar-link[data-page-target]"
        );


    /* ========================================================
       CLIQUE NOS ITENS DA SIDEBAR
       ======================================================== */

    links.forEach(
        (link) => {

            link.addEventListener(

                "click",

                (event) => {


                    /*
                       Impede o comportamento padrão:

                       href="#sectors"

                       Sem isso o navegador simplesmente
                       rolaria a página.
                    */

                    event.preventDefault();


                    /*
                       Obtém o destino do menu.

                       Exemplo:

                       data-page-target="sectors"
                    */

                    const pageId =
                        link.dataset
                            .pageTarget;


                    if (!pageId) {

                        return;

                    }


                    /*
                       Mostra somente a página selecionada.
                    */

                    showPage(

                        pageId,

                        true

                    );

                }

            );

        }
    );


    /* ========================================================
       PÁGINA INICIAL
       ======================================================== */

    /*
       Se a URL já possuir hash:

       localhost:8000/#power

       abrirá diretamente Power / Data Center.
    */

    const hashPage =
        window.location
            .hash
            .replace(
                "#",
                ""
            )
            .trim();


    /*
       Verificamos se o hash é uma
       das páginas permitidas.
    */

    const initialPage =
        PAGE_IDS.includes(
            hashPage
        )

            ? hashPage

            : "overview";


    /*
       Exibe a página inicial.
    */

    showPage(

        initialPage,

        false

    );


    /* ========================================================
       BOTÕES VOLTAR / AVANÇAR
       ======================================================== */

    window.addEventListener(

        "popstate",

        () => {


            const pageId =
                window.location
                    .hash
                    .replace(
                        "#",
                        ""
                    )
                    .trim();


            showPage(

                PAGE_IDS.includes(
                    pageId
                )

                    ? pageId

                    : "overview",

                false

            );

        }

    );

}


/* ============================================================
   INICIALIZAÇÃO PRINCIPAL
   ============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        /*
           Replica os 15 ícones da sidebar nos
           respectivos títulos das páginas.
        */
        syncPageTitleIcons();

        initPageNavigation();

        carregarRadar();

    }
);
