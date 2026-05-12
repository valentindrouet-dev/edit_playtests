import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict, Counter

from engine.simulator import run_simulation, simulate_game
from engine.loader import load_plan_cards, load_intention_cards
from engine.scoring import score_banc
from engine.intentions import score_intentions, evaluate_intention

st.set_page_config(page_title="EDIT — Playtests", layout="wide")
st.title("🎬 EDIT — Plateforme de Simulation")

# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.header("Paramètres")
n_players = st.sidebar.selectbox("Nombre de joueuses", [2, 3, 4], index=0)
strategy = st.sidebar.selectbox("Stratégie", ["greedy", "random"], index=0,
                                 help="greedy = maximise le score plan à chaque pose ; random = placement aléatoire")
n_games = st.sidebar.slider("Nombre de parties simulées", 100, 5000, 1000, step=100)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Distribution des Scores",
    "🃏 Analyse des Cartes Plan",
    "🎯 Analyse des Intentions",
    "🔍 Partie Détaillée",
    "📋 Liste des Cartes",
])

# ── TAB 1 : Score Distribution ────────────────────────────────────────────────
with tab1:
    if st.button("Lancer la simulation", key="sim_btn"):
        with st.spinner(f"Simulation de {n_games} parties…"):
            records = run_simulation(n_games=n_games, n_players=n_players, strategy=strategy)
        df = pd.DataFrame(records)
        st.session_state["df"] = df
        st.success(f"{n_games} parties simulées.")

    if "df" in st.session_state:
        df = st.session_state["df"]

        col1, col2, col3 = st.columns(3)
        col1.metric("Score moyen", f"{df['total'].mean():.1f}")
        col2.metric("Score médian", f"{df['total'].median():.0f}")
        col3.metric("Score max observé", f"{df['total'].max()}")

        col4, col5 = st.columns(2)
        with col4:
            fig = px.histogram(df, x="total", nbins=40, color_discrete_sequence=["#E63946"],
                               title="Distribution des scores totaux")
            fig.update_layout(bargap=0.1)
            st.plotly_chart(fig, use_container_width=True)

        with col5:
            fig2 = px.box(df, y="total", x="player",
                          title="Score par joueuse (toutes parties)",
                          color="player", color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig2, use_container_width=True)

        col6, col7 = st.columns(2)
        with col6:
            fig3 = px.scatter(df, x="plan_total", y="intention_total", opacity=0.3,
                              title="Plans vs Intentions",
                              labels={"plan_total": "Points Plans", "intention_total": "Points Intentions"})
            st.plotly_chart(fig3, use_container_width=True)

        with col7:
            fig4 = px.histogram(df, x="intentions_succeeded", nbins=10,
                                title="Intentions réussies par joueuse",
                                color_discrete_sequence=["#457B9D"])
            st.plotly_chart(fig4, use_container_width=True)

        with st.expander("Données brutes"):
            st.dataframe(df.describe())

    else:
        st.info("Lance la simulation pour afficher les résultats.")

# ── TAB 2 : Card Analysis ─────────────────────────────────────────────────────
with tab2:
    st.subheader("Potentiel de score des Cartes Plan")
    st.markdown(
        "Évalue le score moyen de chaque plan visible sur 2 000 bancs aléatoires de 9 cartes."
    )

    @st.cache_data
    def compute_card_stats(n_samples: int = 2000):
        import random
        all_cards = load_plan_cards()
        plan_scores = defaultdict(list)

        for _ in range(n_samples):
            random.shuffle(all_cards)
            hand = all_cards[:9]
            from engine.simulator import _random_place
            banc = _random_place(hand)
            result = score_banc(banc)
            for entry in result["per_plan"]:
                plan_scores[entry["plan_id"]].append(entry["points"])

        rows = []
        for pid, scores in sorted(plan_scores.items()):
            rows.append({
                "Plan ID": pid,
                "Moyenne": round(sum(scores) / len(scores), 2),
                "Max": max(scores),
                "Min": min(scores),
                "N": len(scores),
            })
        return pd.DataFrame(rows)

    card_df = compute_card_stats()
    card_df_sorted = card_df.sort_values("Moyenne", ascending=False)

    fig5 = px.bar(card_df_sorted, x="Plan ID", y="Moyenne",
                  title="Score moyen par plan (sur 2 000 bancs aléatoires)",
                  color="Moyenne", color_continuous_scale="RdYlGn")
    st.plotly_chart(fig5, use_container_width=True)

    st.dataframe(card_df_sorted, use_container_width=True)

    # Card detail
    st.subheader("Détail d'une carte")
    all_cards = load_plan_cards()
    card_ids = [c.card_id for c in all_cards]
    selected_id = st.selectbox("Carte", card_ids)
    card = next(c for c in all_cards if c.card_id == selected_id)
    for plan in card.plans:
        st.markdown(f"**{plan.plan_id}** — {plan.frame_type} | Genre: {plan.genre or '—'} | Contenu: {', '.join(plan.content)}")
        for rule in plan.scoring:
            st.markdown(f"  - `{rule.type}` {rule.attribute} → {rule.points} pts")

# ── TAB 3 : Intentions Analysis ───────────────────────────────────────────────
with tab3:
    st.subheader("Taux de réussite des Cartes Intention")

    @st.cache_data
    def compute_intention_stats(n_samples: int = 2000):
        import random
        all_cards = load_plan_cards()
        all_intentions = load_intention_cards()
        success_counts = defaultdict(int)

        for _ in range(n_samples):
            random.shuffle(all_cards)
            hand = all_cards[:9]
            from engine.simulator import _random_place
            banc = _random_place(hand)
            for intent in all_intentions:
                if evaluate_intention(intent, banc):
                    success_counts[intent.card_id] += 1

        rows = []
        for intent in all_intentions:
            rate = success_counts[intent.card_id] / n_samples * 100
            rows.append({
                "ID": intent.card_id,
                "Titre": intent.title,
                "Type": intent.type,
                "Points": intent.points,
                "Taux (%)": round(rate, 1),
            })
        return pd.DataFrame(rows)

    intent_df = compute_intention_stats()

    col_a, col_b = st.columns(2)
    with col_a:
        fig6 = px.bar(
            intent_df.sort_values("Taux (%)"),
            x="Taux (%)", y="Titre", orientation="h",
            color="Type",
            title="Taux de réussite par intention (montage aléatoire)",
            color_discrete_map={
                "THEMATIQUE": "#2A9D8F",
                "NARRATIVE": "#E9C46A",
                "TECHNIQUE": "#E76F51",
            },
            height=700,
        )
        st.plotly_chart(fig6, use_container_width=True)

    with col_b:
        fig7 = px.scatter(
            intent_df, x="Taux (%)", y="Points",
            text="Titre", color="Type",
            title="Difficulté vs Valeur",
            color_discrete_map={
                "THEMATIQUE": "#2A9D8F",
                "NARRATIVE": "#E9C46A",
                "TECHNIQUE": "#E76F51",
            },
        )
        fig7.update_traces(textposition="top center", textfont_size=9)
        st.plotly_chart(fig7, use_container_width=True)

    st.dataframe(intent_df.sort_values("Taux (%)"), use_container_width=True)

# ── TAB 4 : Detailed Game ─────────────────────────────────────────────────────
with tab4:
    st.subheader("Inspecter une partie simulée")
    if st.button("Simuler une partie", key="one_game"):
        results = simulate_game(n_players=n_players, strategy=strategy)
        st.session_state["game_results"] = results

    if "game_results" in st.session_state:
        results = st.session_state["game_results"]
        for r in results:
            with st.expander(f"Joueuse {r['player']} — {r['total']} pts", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Plans", r["plan_score"]["total"])
                col2.metric("Intentions", r["intention_score"]["total"])
                col3.metric("Total", r["total"])

                st.markdown("**Banc de Montage :**")
                banc_rows = []
                for entry in r["plan_score"]["per_plan"]:
                    banc_rows.append({
                        "Plan": entry["plan_id"],
                        "Cadrage": entry["frame_type"],
                        "Genre": entry["genre"] or "—",
                        "Contenu": ", ".join(entry["content"]),
                        "Face ↓": "Oui" if entry["face_down"] else "Non",
                        "Points": entry["points"],
                        "Détail": str(entry["breakdown"]),
                    })
                st.dataframe(pd.DataFrame(banc_rows), use_container_width=True)

                st.markdown("**Intentions :**")
                intent_rows = []
                for it in r["intention_score"]["intentions"]:
                    intent_rows.append({
                        "Titre": it["title"],
                        "Type": it["type"],
                        "Partagée": "Oui" if it["shared"] else "Non",
                        "Réussie": "✅" if it["success"] else "❌",
                        "Points gagnés": it["earned"],
                        "Valeur": it["points"],
                    })
                st.dataframe(pd.DataFrame(intent_rows), use_container_width=True)
    else:
        st.info("Clique sur 'Simuler une partie' pour inspecter un résultat.")

# ── TAB 5 : Card Gallery ──────────────────────────────────────────────────────
with tab5:
    GENRE_COLORS = {
        "Action":   {"bg": "#7B1D1D", "badge": "#E63946", "text": "#FFD6D6"},
        "Policier": {"bg": "#1A2744", "badge": "#457B9D", "text": "#D6E8FF"},
        "Suspense": {"bg": "#2E1A47", "badge": "#9B5DE5", "text": "#EDD6FF"},
        None:       {"bg": "#1C1C1C", "badge": "#555555", "text": "#DDDDDD"},
    }
    CONTENT_ICONS = {
        "HEROINE":       ("👩", "Héroïne"),
        "ENNEMI":        ("💀", "Ennemi"),
        "ALLIE":         ("🤝", "Allié"),
        "ARME":          ("🔫", "Arme"),
        "OBJET":         ("👜", "Objet"),
        "VOITURE":       ("🚗", "Voiture"),
        "VIDE":          ("⬛", "Vide"),
        "PLAN_ACTION":   ("💥", "Plan Action"),
        "PLAN_SUSPENSE": ("😰", "Plan Suspense"),
    }
    FRAME_LABELS = {
        "PLAN_LARGE": "PLAN LARGE",
        "PLAN_MOYEN": "PLAN MOYEN",
        "GROS_PLAN":  "GROS PLAN",
    }

    def _rule_label(rule) -> str:
        attr = rule.attribute.replace("_", " ")
        if rule.type == "GAUCHE":
            return f"◄ +{rule.points} si {attr}"
        if rule.type == "DROITE":
            return f"+{rule.points} si {attr} ►"
        return f"+{rule.points}/× {attr} (banc)"

    def _plan_html(plan, width_pct: int) -> str:
        c = GENRE_COLORS[plan.genre]
        icons = " ".join(
            f'<span title="{CONTENT_ICONS.get(x, (x, x))[1]}">{CONTENT_ICONS.get(x, ("?", x))[0]}</span>'
            for x in plan.content
        )
        rules_html = "".join(
            f'<div style="font-size:0.7rem;color:#aaa;line-height:1.4">{_rule_label(r)}</div>'
            for r in plan.scoring
        )
        frame_label = FRAME_LABELS.get(plan.frame_type, plan.frame_type)
        genre_label = plan.genre or "—"
        return f"""
        <div style="
            width:{width_pct}%;
            background:{c['bg']};
            border:1px solid {c['badge']};
            border-radius:6px;
            padding:8px;
            box-sizing:border-box;
            display:flex;
            flex-direction:column;
            gap:4px;
        ">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="
                    background:{c['badge']};color:white;
                    border-radius:4px;padding:1px 6px;
                    font-size:0.65rem;font-weight:bold;letter-spacing:.05em
                ">{frame_label}</span>
                <span style="
                    background:#333;color:{c['text']};
                    border-radius:4px;padding:1px 6px;
                    font-size:0.65rem
                ">{genre_label}</span>
            </div>
            <div style="font-size:1.1rem;letter-spacing:.15em;margin:2px 0">{icons}</div>
            <div style="font-size:0.7rem;color:#ccc">{' • '.join(plan.content)}</div>
            <hr style="border-color:#444;margin:4px 0"/>
            {rules_html}
        </div>
        """

    def render_physical_card(card) -> str:
        card_label = f"#{card.card_id}"
        if card.physical_type == "PLAN_LARGE":
            inner = _plan_html(card.plans[0], 100)
        else:
            # GROS_PLAN = 1/3, PLAN_MOYEN = 2/3
            a, b = card.plans[0], card.plans[1]
            if a.frame_type == "GROS_PLAN":
                gp, pm = a, b
                gp_pct, pm_pct = 32, 66
            else:
                gp, pm = b, a
                gp_pct, pm_pct = 32, 66
            inner = f"""
            <div style="display:flex;gap:4px;width:100%">
                {_plan_html(gp, gp_pct)}
                {_plan_html(pm, pm_pct)}
            </div>
            """
        return f"""
        <div style="
            background:#111;
            border:1px solid #333;
            border-radius:8px;
            padding:8px;
            margin-bottom:12px;
        ">
            <div style="
                font-size:0.7rem;color:#666;margin-bottom:4px;
                font-family:monospace
            ">{card_label} — {card.physical_type}</div>
            {inner}
        </div>
        """

    all_cards_gallery = load_plan_cards()

    filter_col1, filter_col2 = st.columns([2, 2])
    with filter_col1:
        filter_type = st.selectbox(
            "Filtrer par type",
            ["Toutes", "PLAN_LARGE", "COMBO"],
            key="gallery_type",
        )
    with filter_col2:
        filter_genre = st.selectbox(
            "Filtrer par genre",
            ["Tous", "Action", "Policier", "Suspense", "—"],
            key="gallery_genre",
        )

    filtered = all_cards_gallery
    if filter_type != "Toutes":
        filtered = [c for c in filtered if c.physical_type == filter_type]
    if filter_genre != "Tous":
        genre_val = None if filter_genre == "—" else filter_genre
        filtered = [
            c for c in filtered
            if any(p.genre == genre_val for p in c.plans)
        ]

    st.markdown(f"**{len(filtered)} carte(s) affichée(s)**")

    cols_per_row = 3
    rows = [filtered[i:i + cols_per_row] for i in range(0, len(filtered), cols_per_row)]
    for row in rows:
        cols = st.columns(cols_per_row)
        for col, card in zip(cols, row):
            with col:
                st.markdown(render_physical_card(card), unsafe_allow_html=True)
