// (hookshot) The start-up screen's numbers (vk_main.cpp, vk_menu.cpp): how far the shaders' preparation is, and about how long
// it has left. Plain C++, no Vulkan: tests/test_startup_progress.py compiles it on its own.
#pragma once

#include <cstddef>
#include <cstdio>
#include <algorithm>
#include <string>

namespace mkwvk {

/// The time left, from the rate over the last few seconds, not from the start: a start after one that was closed part-way skips
/// what is on disk already in a second or two, and that burst would have promised the rest at the same speed. Nothing is said
/// before a sixth is done (the programs differ a lot: on an RTX 3090 the first 1,500 of 32,000 took half a minute, the next 10,000
/// ten seconds, and the early estimates said 83 minutes for a 70-second job), and what is said is smoothed over about 8 s
/// (it went 1 min, 5 min, 1 min from one 10-second line to the next)
struct ProgressClock {
    static constexpr int kSamples = 64;
    static constexpr double kWindow = 15.0;    // (seconds the rate is taken over)
    static constexpr double kFirst = 3.0;      // (seconds of samples before any estimate)
    static constexpr double kMinShare = 1.0 / 6;
    static constexpr double kSmooth = 8.0;     // (seconds: the estimate's time constant)
    double t[kSamples]{};
    size_t done[kSamples]{};
    int n = 0, head = 0;   // (the samples, oldest at head)
    double last_note = -1, shown = -1;

    void reset() { n = head = 0, last_note = shown = -1; }
    /// A sample: at seconds t_now, done of total (four a second at most are kept)
    void note(double t_now, size_t done_now, size_t total) {
        if (n && done_now < done[(head + n - 1) % kSamples]) reset();   // (a new stage)
        if (last_note >= 0 && t_now - last_note < 0.25) return;
        const double dt = last_note < 0 ? 0 : t_now - last_note;
        last_note = t_now;
        if (n == kSamples) head = (head + 1) % kSamples, n--;
        t[(head + n) % kSamples] = t_now, done[(head + n) % kSamples] = done_now, n++;
        while (n > 2 && t_now - t[(head + 1) % kSamples] >= kWindow) head = (head + 1) % kSamples, n--;
        const double raw = estimate(total);
        if (raw < 0) shown = -1;
        else if (shown < 0 || raw == 0) shown = raw;   // (the first one, or all done)
        else {
            shown = shown > dt ? shown - dt : 0;   // (time passing)
            shown += (raw - shown) * (dt < kSmooth ? dt / kSmooth : 1.0);
        }
    }
    /// Seconds left, or a negative number when it cannot be said yet
    double left() const { return shown; }
    /// The rate over the window alone, unsmoothed
    double estimate(size_t total) const {
        if (n < 2) return -1;
        const int last = (head + n - 1) % kSamples;
        const double span = t[last] - t[head];
        if (done[last] >= total) return 0;
        if (span < kFirst || done[last] <= done[head] || (double)done[last] < (double)total * kMinShare) return -1;
        const double rate = (double)(done[last] - done[head]) / span;
        return (double)(total - done[last]) / rate;
    }
};

/// 12345 as "12,345"
inline std::string with_commas(size_t v) {
    std::string s = std::to_string(v);
    for (int i = (int)s.size() - 3; i > 0; i -= 3) s.insert((size_t)i, ",");
    return s;
}

/// "about 40 s left": up to 5 s under a minute, whole minutes above; empty when unknown
/// (Ocarina Reborn) the text in the game's language (HOS_LANGUAGE: the launcher's Game language), else as it is
inline const char* ocr_tr(const char* en) {
    static const char* const en_[] = {"a few seconds left", "about %d s left", "about %d min left", "Closing", "Keeping what is prepared for the next start", "Starting the game", "STEP 1 OF 2", "STEP 2 OF 2", "Preparing shaders", "Building pipelines", "Loading pipelines", "This happens once after an update. Closing the window keeps what is done.", "Reading the game's shaders", "Reading the pipeline notes", "Loading the shader cache", " pipelines", " shaders"};
    static const char* const de_[] = {"Ein paar Sekunden", "noch etwa %d s", "noch etwa %d min", "Wird beendet", "Der vorbereitete Stand bleibt für den nächsten Start", "Spiel wird gestartet", "SCHRITT 1 VON 2", "SCHRITT 2 VON 2", "Shader werden vorbereitet", "Pipelines werden gebaut", "Pipelines werden geladen", "Das passiert nach einem Update nur einmal. Schließt du das Fenster, bleibt der Stand erhalten.", "Shader des Spiels werden gelesen", "Pipeline-Notizen werden gelesen", "Shader-Cache wird geladen", " Pipelines", " Shader"};
    static const char* const fr_[] = {"Quelques secondes", "environ %d s restantes", "environ %d min restantes", "Fermeture", "Ce qui est préparé est gardé pour le prochain lancement", "Lancement du jeu", "ÉTAPE 1 SUR 2", "ÉTAPE 2 SUR 2", "Préparation des shaders", "Construction des pipelines", "Chargement des pipelines", "Cela n'arrive qu'une fois après une mise à jour. Fermer la fenêtre garde la progression.", "Lecture des shaders du jeu", "Lecture des notes de pipelines", "Chargement du cache de shaders", " pipelines", " shaders"};
    static const char* const es_[] = {"Unos segundos", "quedan unos %d s", "quedan unos %d min", "Cerrando", "Lo preparado se guarda para el próximo inicio", "Iniciando el juego", "PASO 1 DE 2", "PASO 2 DE 2", "Preparando shaders", "Creando pipelines", "Cargando pipelines", "Esto solo ocurre una vez tras una actualización. Cerrar la ventana conserva el progreso.", "Leyendo los shaders del juego", "Leyendo las notas de pipelines", "Cargando la caché de shaders", " pipelines", " shaders"};
    static const char* const it_[] = {"Pochi secondi", "circa %d s rimanenti", "circa %d min rimanenti", "Chiusura", "Quanto preparato resta per il prossimo avvio", "Avvio del gioco", "PASSO 1 DI 2", "PASSO 2 DI 2", "Preparazione degli shader", "Creazione delle pipeline", "Caricamento delle pipeline", "Succede solo una volta dopo un aggiornamento. Chiudere la finestra mantiene i progressi.", "Lettura degli shader del gioco", "Lettura delle note delle pipeline", "Caricamento della cache degli shader", " pipeline", " shader"};
    static const char* const pt_[] = {"Alguns segundos", "cerca de %d s restantes", "cerca de %d min restantes", "Fechando", "O que foi preparado fica para o próximo início", "Iniciando o jogo", "ETAPA 1 DE 2", "ETAPA 2 DE 2", "Preparando shaders", "Criando pipelines", "Carregando pipelines", "Isso só acontece uma vez após uma atualização. Fechar a janela mantém o progresso.", "Lendo os shaders do jogo", "Lendo as notas de pipelines", "Carregando o cache de shaders", " pipelines", " shaders"};
    static const char* const nl_[] = {"Een paar seconden", "nog ongeveer %d s", "nog ongeveer %d min", "Afsluiten", "Wat klaar is, blijft bewaard voor de volgende start", "Spel wordt gestart", "STAP 1 VAN 2", "STAP 2 VAN 2", "Shaders voorbereiden", "Pipelines bouwen", "Pipelines laden", "Dit gebeurt maar één keer na een update. Het venster sluiten bewaart de voortgang.", "Shaders van het spel lezen", "Pipeline-notities lezen", "Shader-cache laden", " pipelines", " shaders"};
    static const char* const* const lang = [] () -> const char* const* {
        const char* l = getenv("HOS_LANGUAGE");
        if (!l) return nullptr;
        if (!strncmp(l, "de", 2)) return de_;
        if (!strncmp(l, "fr", 2)) return fr_;
        if (!strncmp(l, "es", 2)) return es_;
        if (!strncmp(l, "it", 2)) return it_;
        if (!strncmp(l, "pt", 2)) return pt_;
        if (!strncmp(l, "nl", 2)) return nl_;
        return nullptr;
    }();
    if (lang)
        for (size_t i = 0; i < sizeof en_ / sizeof *en_; i++)
            if (!strcmp(en, en_[i])) return lang[i];
    return en;
}
inline std::string left_text(double secs) {
    if (secs < 0) return "";
    char b[48];
    if (secs < 10) return ocr_tr("a few seconds left");
    if (secs < 55) snprintf(b, sizeof b, ocr_tr("about %d s left"), (int)((secs + 4.999) / 5) * 5);
    else snprintf(b, sizeof b, ocr_tr("about %d min left"), secs < 90 ? 1 : (int)(secs / 60 + 0.5));
    return b;
}

/// The version line from the build's name (nx2/version.py, "v2.0.5 (source 1a2b3c4d)"): the release alone, "v2.0.5"; a build
/// between releases ("v2.0.5-2-g619c897-dirty", git describe) shows as "v2.0.5 dev"; anything else as it is
inline std::string version_text(std::string name) {
    if (const size_t at = name.find(" ("); at != std::string::npos) name.resize(at);
    size_t i = 0;
    if (name.size() > 1 && name[0] == 'v') {
        int dots = 0;
        for (i = 1; i < name.size() && ((name[i] >= '0' && name[i] <= '9') || name[i] == '.'); i++) dots += name[i] == '.';
        if (dots == 2 && i < name.size() && name[i] == '-') return name.substr(0, i) + " dev";
    }
    return name;
}

/// "32%": rounded down, and 99% until all is done
inline std::string percent_text(size_t done, size_t total) {
    if (!total) return "";
    size_t p = done >= total ? 100 : done * 100 / total;
    if (p > 99 && done < total) p = 99;
    return std::to_string(p) + "%";
}

/// "32%" of a fraction: rounded down, and 99% until it is 1
inline std::string percent_of(double f) {
    if (f < 0) return "";
    int p = f >= 1 ? 100 : (int)(f * 100);
    if (p > 99 && f < 1) p = 99;
    return std::to_string(p) + "%";
}

/// What the start-up screen shows (vk_menu.cpp draw_startup draws it)
struct StartupView {
    std::string version;            // ("v2.0.5"; empty: the build's)
    std::string step, title, pct;   // ("STEP 1 OF 2", "Preparing shaders", "32%"); an empty title: the wordmark alone
    std::string left, right;        // (under the bar: "12,345 / 38,809 shaders", "about 40 s left")
    std::string hint;
    double fraction = -1;           // (the bar, 0 to 1; negative: none)
    bool operator==(const StartupView&) const = default;
};

/// The state of the start: stage 0 the shader programs, 1 the pipelines the notes predict, 2 the noted pipelines; done of total
/// in it (total 0: not counted yet); left the seconds left (negative: unknown); prepared: this start prepares programs (a first
/// start after an update: two steps, else the pipelines alone); secs since the window opened
struct StartupState {
    int stage = 0;
    size_t done = 0, total = 0;
    double left = -1, secs = 0;
    bool prepared = false, finished = false, stopping = false;
    double whole = -1;   // (the bar over every part, PrepareBar::fraction; negative: the bar is this part's done of total)
};

/// (hookshot) The whole preparation on one bar: its parts, 0 the shader programs, 1 the pipelines the notes predict, 2 the noted
/// pipelines, each counted in what one of it costs (kCost, in shader programs' time) and each in the total from the start. The
/// predicted pipelines were a step of their own after a full bar: the bar sat at 100% while thousands of them were built. A part
/// not counted yet stands in the total at its guess (prepare_guess: from the files on disk), and at its count once it reports one;
/// a part that does not run (a start with nothing to prepare) is skipped, out of the total. The bar never goes back, and reaches
/// 1 only when every part has
struct PrepareBar {
    // (an RTX 3090, 24 threads, a cold driver cache: 38,809 programs translated, their compute pipelines warmed, in 131 s, ~295 a
    // second; 43,414 predicted pipelines built in 306 s, ~142 a second: a pipeline costs about two programs. Only the shares
    // matter: the time left is taken from the bar's own rate)
    static constexpr double kCost[3] = {1.0, 2.0, 2.0};
    size_t done[3]{}, total[3]{};
    bool counted[3]{}, skipped[3]{};
    double shown = 0;

    /// A part's guess, until it is counted
    void guess(int part, size_t n) {
        if (!counted[part] && !skipped[part]) total[part] = n;
    }
    /// A part that does not run
    void skip(int part) { skipped[part] = true, done[part] = total[part] = 0; }
    /// A part's progress (done of total, its count now); the parts before it are over
    void at(int part, size_t d, size_t t) {
        for (int k = 0; k < part; k++)
            if (!skipped[k]) counted[k] = true, done[k] = total[k];
        counted[part] = true, total[part] = t, done[part] = std::min(d, t);
    }
    /// The parts before this one over (it is not counted yet)
    void reach(int part) {
        for (int k = 0; k < part; k++)
            if (!skipped[k]) counted[k] = true, done[k] = total[k];
    }
    /// Every part over
    void finish() {
        for (int k = 0; k < 3; k++)
            if (!skipped[k]) counted[k] = true, done[k] = total[k];
    }
    double units_done() const { return done[0] * kCost[0] + done[1] * kCost[1] + done[2] * kCost[2]; }
    double units_total() const { return total[0] * kCost[0] + total[1] * kCost[1] + total[2] * kCost[2]; }
    bool over() const {
        for (int k = 0; k < 3; k++)
            if (!skipped[k] && (!counted[k] || done[k] < total[k])) return false;
        return true;
    }
    /// 0 to 1: never back, and under 1 while any part is not over
    double fraction() {
        const double all = units_total();
        double f = all > 0 ? units_done() / all : 0;
        if (!over()) f = std::min(f, 0.999);
        else f = 1;
        shown = std::max(shown, f);
        return shown;
    }
};

/// The screen for a state. The first second shows the wordmark alone: a start with next to nothing to prepare is over by then
inline StartupView startup_view(const StartupState& s) {
    StartupView v;
    if (s.stopping) {
        v.title = ocr_tr("Closing");
        v.left = ocr_tr("Keeping what is prepared for the next start");
        return v;
    }
    if (s.finished) {
        if (s.secs >= 1.0) v.title = ocr_tr("Starting the game");
        return v;
    }
    if (s.secs < 1.0) return v;
    const bool pipelines = s.stage > 0;
    if (s.prepared) v.step = ocr_tr(pipelines ? "STEP 2 OF 2" : "STEP 1 OF 2");
    v.title = ocr_tr(!pipelines ? "Preparing shaders" : s.prepared ? "Building pipelines" : "Loading pipelines");
    if (s.prepared) v.hint = ocr_tr("This happens once after an update. Closing the window keeps what is done.");
    if (!s.total) {
        v.left = ocr_tr(!pipelines ? "Reading the game's shaders" : s.stage == 1 ? "Reading the pipeline notes" : "Loading the shader cache");
        if (s.whole >= 0) v.fraction = s.whole, v.pct = percent_of(s.whole), v.right = left_text(s.left);
        return v;
    }
    v.fraction = s.whole >= 0 ? s.whole : (double)std::min(s.done, s.total) / (double)s.total;
    v.pct = s.whole >= 0 ? percent_of(s.whole) : percent_text(s.done, s.total);
    v.left = with_commas(s.done) + " / " + with_commas(s.total) + ocr_tr(pipelines ? " pipelines" : " shaders");
    v.right = left_text(s.left);
    return v;
}

} // namespace mkwvk
