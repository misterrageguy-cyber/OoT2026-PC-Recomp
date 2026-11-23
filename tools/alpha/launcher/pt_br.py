"""The launcher in Brazilian Portuguese: the English of every T(German, English) and German/English table, in pt-BR. tr() is
the English side's way through: in German and English it returns its text as it is, in pt-BR the translation, and English
where a text has none here (so a new English text shows until it is added). FORMATS are the texts with values filled in at run
time (f-strings): {} in the key is one value, {0}, {1}... in the translation the same values in order."""
import re

UI_LANG = ['de']   # the launcher's language (launcher.py UI_LANG): 'de', 'en' or 'pt-BR'

FORMATS = {
    'Virtual display driver "{}" detected. If its application (e.g. Virtual Desktop) is running, test with that application closed for comparison.':
        'Driver de tela virtual "{0}" detectado. Se o programa dele (por exemplo, Virtual Desktop) estiver aberto, teste com ele fechado para comparar.',
    'The game ran on "{}" instead of "{}". In Windows → Graphics settings, set Ocarina Reborn to "High performance".':
        'O jogo rodou na "{0}" em vez da "{1}". Em Windows → Configurações de gráficos, coloque o Ocarina Reborn em "Alto desempenho".',
    'Smooth: {} fps median over {} minutes of play.': 'Jogo fluido: mediana de {0} FPS em {1} minutos de jogo.',
    '{} of the time under 55 fps (median {}, lowest {}).': '{0} do tempo abaixo de 55 FPS (mediana {1}, mínimo {2}).',
    'Video memory nearly full ({} of {} GB): lower Texture memory one step.':
        'Memória de vídeo quase cheia ({0} de {1} GB): baixe a Memória de texturas em um nível.',
    '{} short hitches over 100 ms, mostly when entering new areas (loading). There are fewer the second time.':
        '{0} engasgos curtos acima de 100 ms, quase sempre ao entrar em áreas novas (carregamento). Na segunda vez são menos.',
    'Processor and graphics card are both at their limit (CPU {} ms, GPU {} ms a frame). Helps: an upscaler for the graphics card, and closing programs in the background.':
        'Processador e placa de vídeo estão no limite (CPU {0} ms, GPU {1} ms por quadro). Ajuda: um upscaler para a placa de vídeo e fechar programas em segundo plano.',
    'Bottleneck: the graphics card ({} ms a frame, CPU {} ms). Helps: an upscaler (NVIDIA DLSS or AMD FSR 3.1, Quality) or a lower render resolution.':
        'Gargalo: a placa de vídeo ({0} ms por quadro, CPU {1} ms). Ajuda: um upscaler (NVIDIA DLSS ou AMD FSR 3.1, Qualidade) ou uma resolução interna menor.',
    'Bottleneck: the processor ({} ms a frame for the renderer, GPU {} ms). Helps: closing programs in the background. An upscaler helps little here.':
        'Gargalo: o processador ({0} ms por quadro no renderizador, GPU {1} ms). Ajuda: fechar programas em segundo plano. Um upscaler ajuda pouco aqui.',
    'The build ended with code {}.': 'O build terminou com o código {0}.',
    'Needs {} GB  •  {} has {} GB free': 'Precisa de {0} GB  •  {1} tem {2} GB livres',
    'New in {}': 'Novidades da {0}',
    'Updating to {}': 'Atualizando para a {0}',
    'Too little measured (at least {} s of play without the menu open). Click Reborn Auto again and play a little longer.':
        'Medição insuficiente (é preciso pelo menos {0} s de jogo sem o menu aberto). Clique em Reborn Auto de novo e jogue um pouco mais.',
    'Page {} of {}': 'Página {0} de {1}',
    'Restore this save?\n\n{}\n\nYour current save is backed up automatically first.':
        'Restaurar este save?\n\n{0}\n\nAntes disso, é feito um backup automático do seu save atual.',
    'Import the save from {}?\n\n{}': 'Importar o save de {0}?\n\n{1}',
    '+ {} older': '+ {0} mais antigos',
    '+ {} more (open the folder)': '+ {0} outros (abra a pasta)',
    'Ocarina Reborn {} is out.\n\n': 'Saiu o Ocarina Reborn {0}.\n\n',
    'Imported {} save slots. Your previous save is backed up as ': '{0} slots de save importados. O backup do seu save anterior está em ',
    'Adjusting enemy health (monsters x{}, bosses x{}) …': 'Ajustando a vida dos inimigos (monstros x{0}, chefes x{1}) …',
    'Downloading … {} / {} MB': 'Baixando … {0} / {1} MB',
    'Frames over 50 ms per minute: {} → {}': 'Quadros acima de 50 ms por minuto: {0} → {1}',
    'Frames over 100 ms per minute: {} → {}': 'Quadros acima de 100 ms por minuto: {0} → {1}',
    'Worst window P99: {} → {} ms': 'P99 da pior janela: {0} → {1} ms',
    '{} actual game fps over {} s of analyzed rendering (generated frames excluded).':
        '{0} FPS reais do jogo em {1} s de renderização analisada (quadros gerados não contam).',
    'Worst 5-second window: P95 {} ms, P99 {} ms. {} frames over 50 ms, including {} over 100 ms.':
        'Pior janela de 5 segundos: P95 {0} ms, P99 {1} ms. {2} quadros acima de 50 ms, dos quais {3} acima de 100 ms.',
    'Renderer CPU {} ms/frame, GPU {} ms/frame; peak reported VRAM use {} GB. CPU time excludes other game logic.':
        'Renderizador: CPU {0} ms/quadro, GPU {1} ms/quadro; pico de VRAM informado {2} GB. O tempo de CPU não inclui o resto da lógica do jogo.',
    'During {} s below 55 fps, renderer CPU time was clearly higher than GPU time. Reduce view distance and grass; test a 60 fps limit.':
        'Durante {0} s abaixo de 55 FPS, o tempo de CPU do renderizador foi bem maior que o da GPU. Reduza a distância de visão e a grama; teste um limite de 60 FPS.',
    'Video memory exceeded 90% of the reported budget for {} s. This can cause stutter. Test a smaller texture cache (including when set to Auto) and close GPU-intensive background programs.':
        'A memória de vídeo passou de 90% do limite informado por {0} s. Isso pode causar engasgos. Teste um cache de texturas menor (inclusive quando estiver em Auto) e feche programas pesados para a GPU em segundo plano.',
    'A comparison needs at least {} s of usable play in each run.': 'Uma comparação precisa de pelo menos {0} s de jogo aproveitável em cada rodada.',
    "NVIDIA DLSS comes from NVIDIA and is under NVIDIA's own license:\n{}\n\nOcarina Reborn may not ship DLSS. If you agree, the launcher downloads NVIDIA's DLSS SDK from NVIDIA's GitHub onto this PC and rebuilds your game with it (like an update; your saves stay).\n\nDo you accept NVIDIA's license?":
        'O NVIDIA DLSS é da NVIDIA e segue a licença própria da NVIDIA:\n{0}\n\nO Ocarina Reborn não pode distribuir o DLSS. Se você concordar, o launcher baixa o DLSS SDK do GitHub da NVIDIA para este PC e recria o seu jogo com ele (como uma atualização; seus saves ficam).\n\nVocê aceita a licença da NVIDIA?',

    # the launcher's helpers: dates, the update button, the Windows trace, errors
    '{} days ago': 'há {0} dias',
    'Update {}': 'Atualizar {0}',
    'Switch to the game. Capture starts in {} s.': 'Volte para o jogo. A gravação começa em {0} s.',
    'Recording: reproduce the problem ({} s remaining).': 'Gravando: reproduza o problema (faltam {0} s).',
    'OSError: {} of {} bytes': 'Download incompleto: {0} de {1} bytes.',
    'the game build stopped (exit code {}); see {}': 'o build do jogo parou (código {0}); veja {1}',
    'Incomplete or wrong ZIP. Expected {}Attack1.wav, Hurt1.wav, Jump1.wav, ...':
        'ZIP incompleto ou errado. Eram esperados {0}Attack1.wav, Hurt1.wav, Jump1.wav, ...',
    'Duplicate classic voice folders: {}': 'Pastas de vozes clássicas duplicadas: {0}',
    'Unrecognized classic voice mod: {}': 'Mod de vozes clássicas não reconhecido: {0}',
    'Expected a mono voice: {}': 'Era esperada uma voz mono: {0}',
    'Unsupported looping voice: {}': 'Voz em loop não suportada: {0}',
    'Missing voice stream: {}': 'Faltando o áudio da voz: {0}',
    'Duplicate voice: {}': 'Voz duplicada: {0}',
    'Voice clip is too large: {}': 'Clipe de voz grande demais: {0}',
    'Expected mono PCM16 WAV: {}': 'Era esperado um WAV PCM16 mono: {0}',
    'Unsupported sample rate or length: {}': 'Taxa de amostragem ou duração não suportada: {0}',
    'Truncated WAV: {}': 'WAV incompleto: {0}',
    '{} exists already': '{0} já existe',
    'unsafe path in the archive: {}': 'caminho inseguro no arquivo compactado: {0}',
    'copy check failed for {}': 'a verificação da cópia falhou em {0}',
    'backup failed: {}': 'o backup falhou: {0}',
    'backup.json unreadable: {}': 'não foi possível ler o backup.json: {0}',
}

TEXT = {
    # PC warnings and tips (advisor.py)
    'The laptop runs on battery: the graphics card slows itself down a lot. Plug in the charger.':
        'O notebook está na bateria: a placa de vídeo reduz bastante o próprio desempenho. Ligue o carregador.',
    'Windows is on the "Power saver" plan. Choose "Balanced" or "High performance" in the power options.':
        'O Windows está no plano "Economia de energia". Escolha "Equilibrado" ou "Alto desempenho" nas opções de energia.',
    'Laptop on the "Balanced" power plan: Windows holds the CPU back. For playing, choose "High performance" (or the maker\'s performance mode) and plug in the charger.':
        'Notebook no plano de energia "Equilibrado": o Windows limita a CPU. Para jogar, escolha "Alto desempenho" (ou o modo de desempenho do fabricante) e ligue o carregador.',
    'Only 16 GB of RAM: the game needs a lot of memory. Close other programs (browser, Discord), set Settings → Memory → RAM guard to "Strong" and "Largest textures" to 1024, and let Windows manage the page file automatically.':
        'Só 16 GB de RAM: o jogo precisa de bastante memória. Feche outros programas (navegador, Discord), coloque Configurações → Memória → Proteção de RAM em "Forte" e "Texturas grandes" em 1024, e deixe o Windows gerenciar o arquivo de paginação automaticamente.',
    'AMD: turn on "AMD Anti-Lag 2" in the Performance tab for a quicker response.':
        'AMD: ative o "AMD Anti-Lag 2" na aba Desempenho para uma resposta mais rápida.',
    'No usable windows yet. Play for at least 30 seconds with the F1 menu closed.':
        'Ainda não há janelas aproveitáveis. Jogue pelo menos 30 segundos com o menu F1 fechado.',
    'AMD: for the best image, choose AMD FSR 4 as the upscaler (Quality tab).':
        'AMD: para a melhor imagem, escolha o AMD FSR 4 como upscaler (aba Qualidade).',
    'NVIDIA: turn on "NVIDIA Reflex" in the Performance tab for a quicker response.':
        'NVIDIA: ative o "NVIDIA Reflex" na aba Desempenho para uma resposta mais rápida.',
    ' You already use an upscaler: set it one step faster (Balanced).':
        ' Você já usa um upscaler: deixe-o um nível mais rápido (Equilibrado).',

    # the build screen (build_screen.py)
    'Preparing the NUP file': 'Preparando o arquivo NUP',
    'Extracting game resources': 'Extraindo os recursos do jogo',
    'Analysing the game code': 'Analisando o código do jogo',
    'Compiling the game': 'Compilando o jogo',
    'Compiling shaders': 'Compilando shaders',
    'Checking the NUP file …': 'Verificando o arquivo NUP …',
    'Extracting game resources …': 'Extraindo os recursos do jogo …',
    'Analysing the game code …': 'Analisando o código do jogo …',
    'Compiling shaders …': 'Compilando shaders …',
    'Finishing the installation …': 'Finalizando a instalação …',
    'Finishing the installation': 'Finalizando a instalação',
    'files': 'arquivos',
    'shaders': 'shaders',
    'The build is running. Please do not close the window.': 'O build está rodando. Por favor, não feche a janela.',
    'The update is being installed. Please do not close the window.': 'A atualização está sendo instalada. Por favor, não feche a janela.',
    'Build started': 'Build iniciado',
    'Build cancelled': 'Build cancelado',
    'Really cancel the build? It can be resumed afterwards.': 'Cancelar o build mesmo? Dá para continuar depois.',
    'Ocarina Reborn was built successfully.': 'O Ocarina Reborn foi criado com sucesso.',
    'Shaders are prepared at the first start of the game.': 'Os shaders são preparados na primeira vez que o jogo abrir.',
    'Unsupported game version. ': 'Versão do jogo não suportada. ',
    'ERROR: ': 'ERRO: ',
    'Build failed: ': 'O build falhou: ',
    'Build cancelled.': 'Build cancelado.',
    'Yes, cancel': 'Sim, cancelar',
    'Cancel': 'Cancelar',
    'Keep building': 'Continuar o build',
    'To the launcher': 'Voltar ao launcher',
    'Back': 'Voltar',
    'Build log': 'Log do build',
    'Installation completed successfully.': 'Instalação concluída com sucesso.',
    'Hide log': 'Ocultar log',
    'Show log': 'Mostrar log',
    'Open log file': 'Abrir arquivo de log',
    'Shaders are prepared at the first start (': 'Os shaders são preparados na primeira vez que o jogo abrir (',
    'Error': 'Erro',
    'Cancelled': 'Cancelado',
    'not needed': 'desnecessário',

    # start-up and diagnostics (diagnostics.py, performance.py)
    'The game folder could not be reserved. Check that the folder is accessible and writable.':
        'Não foi possível reservar a pasta do jogo. Verifique se a pasta está acessível e se é possível gravar nela.',
    'The game or shader preparation is already running in this game folder. Close the game or let preparation finish, then try again. Your shader caches have not been changed.':
        'O jogo ou a preparação de shaders já está rodando nesta pasta. Feche o jogo ou espere a preparação terminar e tente de novo. Seus caches de shaders não foram alterados.',
    'No Vulkan 1.3 graphics device was available to the game. This can leave a black screen while audio and inputs still work. Check driver support with your GPU or laptop manufacturer. Lower graphics settings or rebuilding shaders cannot add the missing Vulkan support.':
        'Nenhum dispositivo gráfico com Vulkan 1.3 estava disponível para o jogo. Isso pode deixar a tela preta enquanto o áudio e os controles continuam funcionando. Confira o suporte do driver com o fabricante da sua GPU ou do notebook. Baixar os gráficos ou recompilar os shaders não adiciona o suporte a Vulkan que falta.',
    'Graphics initialization failed; the screen stays black even though audio may continue. Close the game and send a Debug Package so we can check the graphics startup failure.':
        'A inicialização dos gráficos falhou; a tela fica preta mesmo que o áudio continue. Feche o jogo e envie um Pacote de debug para a gente verificar a falha na inicialização gráfica.',
    'Low available RAM or Windows commit headroom was measured during play. Set Streaming and memory to Lower memory, keep RAM guard on Strong, and close unnecessary background apps. Rebuilding shaders will not fix this.':
        'Foi medida pouca RAM livre ou pouca margem de memória do Windows durante o jogo. Coloque Streaming e memória em Menos memória, deixe a Proteção de RAM em Forte e feche apps desnecessários em segundo plano. Recompilar os shaders não resolve isso.',
    'Windows memory was exhausted: the renderer reported host-memory errors or Windows had to grow the page file. Set RAM guard to Strong, close background programs and keep the Windows page file system-managed.':
        'A memória do Windows se esgotou: o renderizador informou erros de memória do sistema ou o Windows precisou aumentar o arquivo de paginação. Coloque a Proteção de RAM em Forte, feche programas em segundo plano e deixe o arquivo de paginação gerenciado pelo sistema.',
    'Windows with the F1 menu open or very few draw calls are excluded. Loading may still be included.':
        'Janelas com o menu F1 aberto ou com pouquíssimas chamadas de desenho não contam. Carregamentos ainda podem estar incluídos.',
    'Measure without generated frames first to establish a comparison.':
        'Meça primeiro sem quadros gerados para ter uma base de comparação.',
    'No clear automatic adjustment. Compare the same scenes again when investigating stutter.':
        'Nenhum ajuste automático claro. Compare as mesmas cenas de novo ao investigar engasgos.',
    'The GPU watchdog stopped the game because submitted graphics work stopped completing. This can happen without a driver-reported device loss. Please test the same area with frame generation off and send a fresh Debug Package. This log alone does not identify the cause or prove a hardware fault.':
        'O watchdog da GPU parou o jogo porque o trabalho gráfico enviado deixou de ser concluído. Isso pode acontecer sem o driver informar perda do dispositivo. Teste a mesma área com a geração de quadros desligada e envie um Pacote de debug novo. Só este log não identifica a causa nem prova defeito de hardware.',
    'The renderer ran out of GPU memory (VK_ERROR_OUT_OF_DEVICE_MEMORY). Set Texture memory to 2 GB and close other GPU-intensive programs. Integrated graphics shares system RAM with the game.':
        'O renderizador ficou sem memória de GPU (VK_ERROR_OUT_OF_DEVICE_MEMORY). Coloque a Memória de texturas em 2 GB e feche outros programas pesados para a GPU. Gráficos integrados dividem a RAM do sistema com o jogo.',
    'The GPU device was lost (VK_ERROR_DEVICE_LOST). Restart the game and send the Debug Package. This error alone does not establish a memory or driver fault.':
        'O dispositivo da GPU foi perdido (VK_ERROR_DEVICE_LOST). Reinicie o jogo e envie o Pacote de debug. Só este erro não comprova falha de memória ou de driver.',
    'Another game or preparation process held the shader program cache. This run could not use it and had to compile shaders again. Close other game instances or let shader preparation finish, then restart once. Do not delete the cache.':
        'Outro processo do jogo ou da preparação estava usando o cache de programas de shader. Esta execução não pôde usá-lo e teve de compilar os shaders de novo. Feche outras instâncias do jogo ou espere a preparação de shaders terminar e reinicie uma vez. Não apague o cache.',
    'Frame generation was active with low actual game fps. High multipliers can further limit the base frame rate. Turn frame generation off for comparison; more generated frames do not fix a low base frame rate.':
        'A geração de quadros estava ativa com poucos FPS reais no jogo. Multiplicadores altos podem limitar ainda mais a taxa de quadros base. Desligue a geração de quadros para comparar; mais quadros gerados não resolvem uma taxa base baixa.',
    'The log reports existing shader/pipeline caches. Do not clear them to fix low fps: new pipelines and asset loading can still cause stutter.':
        'O log mostra caches de shaders/pipelines já existentes. Não os apague para resolver FPS baixo: pipelines novos e carregamento de recursos ainda podem causar engasgos.',
    'Suggestions need at least 30 seconds of usable play measurements.':
        'As sugestões precisam de pelo menos 30 segundos de medições de jogo aproveitáveis.',
    'Settings changed since measurement: play another session first.':
        'As configurações mudaram desde a medição: jogue outra sessão primeiro.',
    'GPU time was high in many steady windows: reduce render resolution by one step.':
        'O tempo de GPU ficou alto em muitas janelas estáveis: reduza a resolução interna em um nível.',
    'GPU memory errors or sustained memory pressure: test a smaller texture cache.':
        'Erros de memória de GPU ou pressão de memória constante: teste um cache de texturas menor.',
    'High renderer CPU time during FPS drops: test one lower step for view distance and grass.':
        'Tempo de CPU alto no renderizador durante quedas de FPS: teste um nível abaixo na distância de visão e na grama.',
    'The current frame-rate limit is above 60: cap it at 60 for the comparison.':
        'O limite de FPS atual está acima de 60: limite em 60 para a comparação.',
    'The preparation did not finish (code {c}). The game builds missing shaders while it plays.':
        'A preparação não terminou (código {c}). O jogo cria os shaders que faltam enquanto você joga.',
    'The game closed because Windows ran out of memory (RAM plus the page file).\n\nClose other programs (browser, Discord, recording tools) and in Windows > System > About > Advanced system settings > Performance > Advanced > Virtual memory choose "Automatically manage paging file size" (or at least 32 GB as the maximum).':
        'O jogo fechou porque o Windows ficou sem memória (RAM mais o arquivo de paginação).\n\nFeche outros programas (navegador, Discord, gravadores de tela) e em Windows > Sistema > Sobre > Configurações avançadas do sistema > Desempenho > Avançado > Memória virtual escolha "Gerenciar automaticamente o tamanho do arquivo de paginação" (ou pelo menos 32 GB como máximo).',

    # the game's settings (game_settings.py): sections, rows, choices and help
    'Display': 'Tela',
    'Quality': 'Qualidade',
    'Performance': 'Desempenho',
    'Memory': 'Memória',
    'Shaders': 'Shaders',
    'Gameplay': 'Jogo',
    'Tunic': 'Túnica',
    'Controls': 'Controles',
    'Audio': 'Áudio',
    'Advanced': 'Avançado',
    'Appearance': 'Aparência',
    'Off': 'Desligado',
    'On': 'Ligado',
    'Fullscreen': 'Tela cheia',
    'Fills the whole screen. The same as F11.': 'Ocupa a tela inteira. O mesmo que F11.',
    'Output resolution': 'Resolução de saída',
    "2048x1152 (game's)": '2048x1152 (do jogo)',
    '720x1280 (9:16 portrait)': '720x1280 (9:16 retrato)',
    '1080x1920 (9:16 portrait)': '1080x1920 (9:16 retrato)',
    '1440x2560 (9:16 portrait)': '1440x2560 (9:16 retrato)',
    '2160x3840 (9:16 portrait)': '2160x3840 (9:16 retrato)',
    'The size of the finished picture, HUD included. Choose a 9:16 resolution for portrait mode; restart the game.':
        'O tamanho da imagem final, com o HUD. Para o modo retrato, escolha uma resolução 9:16; reinicie o jogo.',
    "Monitor's shape": 'Formato do monitor',
    "The camera's shape on screens that are not 16:9.": 'O formato da câmera em telas que não são 16:9.',
    'Window scaling filter': 'Filtro de escala',
    'How the picture is fitted to the window when sizes differ.': 'Como a imagem se ajusta à janela quando os tamanhos são diferentes.',
    'Whether a frame waits for the display. On: no tearing, a little more input delay. Auto adapts.':
        'Se o quadro espera pela tela. Ligado: sem tearing, um pouco mais de atraso nos comandos. Auto se adapta.',
    'Expanded': 'Expandido',
    "Native (the game's)": 'Nativo (do jogo)',
    'HDR10 on an HDR display (Windows: HDR on).': 'HDR10 em uma tela HDR (Windows: HDR ligado).',
    'HDR paper white': 'Branco de papel HDR',
    'How bright white is with HDR. Around 200 for a normal room.': 'O brilho do branco com HDR. Por volta de 200 para um ambiente normal.',
    'HDR peak brightness': 'Brilho máximo HDR',
    "The brightest highlights with HDR: your display's peak.": 'Os pontos mais claros com HDR: o pico da sua tela.',
    'Quality preset': 'Perfil de qualidade',
    'Custom': 'Personalizado',
    'Minimum (4GB)': 'Mínimo (4GB)',
    'Low (6GB)': 'Baixo (6GB)',
    'Balanced (8GB)': 'Equilibrado (8GB)',
    'High (12GB)': 'Alto (12GB)',
    'Sets scaling, frame generation and memory limits for a GPU with that much memory.':
        'Ajusta a escala, a geração de quadros e os limites de memória para uma GPU com essa quantidade de memória.',
    "Game's own": 'Do jogo',
    'FSR 3.1.6 uses the included AMD runtime on supported GPUs. Select 67% for Quality. FSR 3.1 remains available as an alternative. AMD FSR 4 on AMD cards its driver offers it for (RX 9000; with a recent driver RX 7000 too); otherwise the game uses its own.':
        'O FSR 3.1.6 usa a biblioteca da AMD incluída, nas GPUs suportadas. Escolha 67% para Qualidade. O FSR 3.1 continua disponível como alternativa. AMD FSR 4 nas placas AMD em que o driver oferece (RX 9000; com driver recente também RX 7000); senão o jogo usa o seu próprio.',
    'DLSS (not available)': 'DLSS (não disponível)',
    'DLAA (not available)': 'DLAA (não disponível)',
    'AMD FSR 4 (not on this graphics card)': 'AMD FSR 4 (indisponível nesta placa de vídeo)',
    'AMD FSR 4 Native AA (not on this graphics card)': 'AMD FSR 4 Native AA (indisponível nesta placa de vídeo)',
    'Render resolution': 'Resolução interna',
    'Auto (dynamic)': 'Auto (dinâmica)',
    '67% (Quality)': '67% (Qualidade)',
    '58% (Balanced)': '58% (Equilibrado)',
    '50% (Performance)': '50% (Desempenho)',
    'The share of the output the 3D is drawn at; the upscaler fills in the rest.':
        'A parte da resolução de saída em que o 3D é desenhado; o upscaler completa o resto.',
    'Sharpness': 'Nitidez',
    'Sharpens the finished picture. Too much shows halos.': 'Deixa a imagem final mais nítida. Em excesso, aparecem halos.',
    'Reborn look': 'Visual Reborn',
    'Off (original colours)': 'Desligado (cores originais)',
    'Vivid': 'Vívido',
    'Warm': 'Quente',
    'Cool': 'Frio',
    'Cinematic': 'Cinematográfico',
    "Ocarina Reborn's colour grade for the finished picture: richer colour and contrast, a warm or cool tone, a soft vignette. Also in game under F1 → Graphics, visible at once. Not with HDR.":
        'O tratamento de cor do Ocarina Reborn na imagem final: cores e contraste mais ricos, um tom quente ou frio, uma vinheta suave. Também no jogo em F1 → Gráficos, aparece na hora. Não funciona com HDR.',
    'A soft glow around bright light: the sun, fire, magic. Added by Ocarina Reborn on the finished picture. Also in F1 → Graphics, visible at once. Not with HDR.':
        'Um brilho suave em volta de luzes fortes: o sol, fogo, magia. Adicionado pelo Ocarina Reborn na imagem final. Também em F1 → Gráficos, aparece na hora. Não funciona com HDR.',
    'FXAA (anti-aliasing)': 'FXAA (anti-aliasing)',
    'Smooths jagged edges on the finished picture. Light on performance; not needed with FSR, which smooths already. Also in F1 → Graphics, visible at once.':
        'Suaviza bordas serrilhadas na imagem final. Leve para o desempenho; não é preciso com FSR, que já suaviza. Também em F1 → Gráficos, aparece na hora.',
    'Low': 'Baixo',
    'Medium': 'Médio',
    'High': 'Alto',
    'View distance': 'Distância de visão',
    'Short': 'Curta',
    'Original': 'Original',
    'Far': 'Longe',
    'Very far': 'Muito longe',
    'Max': 'Máxima',
    'How far trees, bushes and detailed models reach. Further costs CPU and GPU time. Also in F1 → Graphics.':
        'Até onde aparecem árvores, arbustos e modelos detalhados. Mais longe custa tempo de CPU e GPU. Também em F1 → Gráficos.',
    'Grass': 'Grama',
    'Less': 'Menos',
    'More': 'Mais',
    'Dense': 'Densa',
    'How much grass grows. Off or Less helps weaker PCs. Also in F1 → Graphics.':
        'Quanta grama aparece. Desligado ou Menos ajuda PCs mais fracos. Também em F1 → Gráficos.',
    'Shadow distance': 'Distância das sombras',
    'How far scenery and characters cast shadows. Further costs GPU time. Also in F1 → Graphics.':
        'Até onde o cenário e os personagens fazem sombra. Mais longe custa tempo de GPU. Também em F1 → Gráficos.',
    'Anisotropic filtering': 'Filtragem anisotrópica',
    'Sharper textures at steep angles, such as paths into the distance.':
        'Texturas mais nítidas em ângulos inclinados, como caminhos que vão para longe.',
    'Texture detail': 'Detalhe das texturas',
    'Standard': 'Padrão',
    'Ultra': 'Ultra',
    'Finer texture levels further away. Ultra can shimmer on fine patterns.':
        'Níveis de textura mais finos à distância. Ultra pode cintilar em padrões finos.',
    'Texture filtering': 'Filtragem de texturas',
    "The game's": 'Do jogo',
    'Smooth': 'Suave',
    'Smooth: every texture filtered, no blocky halos in smoke, fog and glows.':
        'Suave: todas as texturas filtradas, sem halos quadriculados em fumaça, névoa e brilhos.',
    'Soft shadows': 'Sombras suaves',
    'Shadow edges blended over four samples instead of hard steps.':
        'Bordas das sombras suavizadas com quatro amostras em vez de degraus marcados.',
    'Frame generation (FSR 3.1)': 'Geração de quadros (FSR 3.1)',
    'Adds generated frames, not actual game frames. High multipliers can limit the base frame rate and increase input delay. Test Off first when investigating stutter. Dialogues and cutscenes use only actual game frames to protect text boxes.':
        'Adiciona quadros gerados, não quadros reais do jogo. Multiplicadores altos podem limitar a taxa de quadros base e aumentar o atraso nos comandos. Ao investigar engasgos, teste primeiro com Desligado. Diálogos e cutscenes usam só quadros reais para proteger as caixas de texto.',
    'Frame pacing': 'Ritmo dos quadros',
    'Shows the frames evenly spaced.': 'Mostra os quadros com espaçamento uniforme.',
    'Frame rate cap': 'Limite de FPS',
    "60 (the console's)": '60 (do console)',
    'The most frames a second the game runs at.': 'O máximo de quadros por segundo em que o jogo roda.',
    'On + Boost': 'Ligado + Boost',
    'Less input delay (NVIDIA only, not with frame generation).': 'Menos atraso nos comandos (só NVIDIA, não com geração de quadros).',
    'Less input delay (AMD only, not with frame generation).': 'Menos atraso nos comandos (só AMD, não com geração de quadros).',
    'Handheld profile': 'Perfil portátil',
    'Runs as if the console were undocked: less work.': 'Roda como se o console estivesse no modo portátil: menos trabalho.',
    'FPS counter': 'Contador de FPS',
    'Frame time': 'Tempo de quadro',
    'Graph': 'Gráfico',
    'Breakdown': 'Detalhamento',
    'Frames per second in game. Frame time, Graph and Breakdown show more: the time a frame takes and where it goes.':
        'Quadros por segundo no jogo. Tempo de quadro, Gráfico e Detalhamento mostram mais: quanto tempo um quadro leva e onde esse tempo é gasto.',
    'Texture saving (test)': 'Economia de texturas (teste)',
    'Stores large, coarsely compressed ASTC texture arrays with fewer mip levels. Reduces their image memory; terrain may look softer. Experimental and off by default. Restart the game. Off restores the original policy.':
        'Guarda arrays grandes de texturas ASTC com compressão grosseira usando menos níveis de mip. Reduz a memória delas; o terreno pode ficar mais suave. Experimental e desligado por padrão. Reinicie o jogo. Desligado volta ao comportamento original.',
    'Texture memory': 'Memória de texturas',
    'Upper limit for the texture cache. More can reduce reloads. The driver limit and shared RAM on integrated graphics can reduce the actual cache size.':
        'Limite máximo do cache de texturas. Mais pode reduzir recarregamentos. O limite do driver e a RAM compartilhada em gráficos integrados podem diminuir o tamanho real do cache.',
    'Pipeline precompile': 'Pré-compilação de pipelines',
    'Builds every pipeline the game used before at the start: less stutter while playing.':
        'Cria na abertura todos os pipelines que o jogo já usou: menos engasgos jogando.',
    'Shader cache': 'Cache de shaders',
    'Keeps compiled shaders on disk. Off: every start compiles everything again.':
        'Guarda os shaders compilados no disco. Desligado: toda abertura compila tudo de novo.',
    'Shader threads': 'Threads de shaders',
    'CPU threads compiling shaders. More is faster but can slow the game down.':
        'Threads da CPU compilando shaders. Mais é mais rápido, mas pode deixar o jogo lento.',
    'Ocarina': 'Ocarina',
    'Fairy Ocarina': 'Ocarina feérica',
    'Ocarina of Time': 'Ocarina do Tempo',
    "Choose the instrument Link uses the next time he takes out an ocarina, as child or adult. Requires an owned ocarina. Original uses the game's instrument. Inventory and story progress are unchanged.":
        'Escolha o instrumento que o Link usa na próxima vez que sacar uma ocarina, como criança ou adulto. Precisa já ter uma ocarina. Original usa o instrumento do jogo. Inventário e progresso da história não mudam.',
    'Unlimited amiibo': 'amiibo ilimitado',
    'Removes the daily amiibo cooldown. Select your own .bin under amiibo and scan again in-game. Off restores normal limits. Tag files and the system clock are unchanged.':
        'Tira a espera diária do amiibo. Escolha o seu próprio .bin em amiibo e escaneie de novo no jogo. Desligado volta aos limites normais. Os arquivos da tag e o relógio do sistema não mudam.',
    'Classic counters (N64)': 'Contadores clássicos (N64)',
    'As on the N64: no count over Link when he picks something up, rupees always shown. Also in F1 → Gameplay.':
        'Como no N64: sem contagem em cima do Link quando ele pega algo, rupias sempre visíveis. Também em F1 → Jogo.',
    'Speedrun timer': 'Cronômetro de speedrun',
    'Real time in the top left corner, paused while the F1 menu is open. Turning it off and on in F1 → Gameplay resets it.':
        'Tempo real no canto superior esquerdo, pausado enquanto o menu F1 está aberto. Desligar e ligar em F1 → Jogo zera o cronômetro.',
    'Death counter': 'Contador de mortes',
    "Shows in the top left corner how often Link's hearts reached zero since the game started.":
        'Mostra no canto superior esquerdo quantas vezes os corações do Link chegaram a zero desde que o jogo começou.',
    'Text speed': 'Velocidade do texto',
    'Normal': 'Normal',
    'Instant': 'Instantânea',
    'How fast the letters of dialogue and messages appear.': 'A rapidez com que as letras dos diálogos e mensagens aparecem.',
    'Text size': 'Tamanho do texto',
    'How large dialogue, Navi and signs are drawn.': 'O tamanho com que diálogos, Navi e placas são desenhados.',
    'Game speed below 60 fps': 'Velocidade do jogo abaixo de 60 FPS',
    'Real time': 'Tempo real',
    'Per frame (slower)': 'Por quadro (mais lenta)',
    'Real time: the game keeps its speed when the fps drop. Per frame: it slows down with the fps, as on the console.':
        'Tempo real: o jogo mantém a velocidade quando o FPS cai. Por quadro: ele fica mais lento junto com o FPS, como no console.',
    'amiibo': 'amiibo',
    'Custom color': 'Cor personalizada',
    'Custom tunic color': 'Cor personalizada da túnica',
    'Choose any color below. Save and restart the game. Original restores the original colors.':
        'Escolha qualquer cor abaixo. Salve e reinicie o jogo. Original volta às cores originais.',
    'Mouse camera': 'Câmera do mouse',
    'As the stick': 'Como o analógico',
    'Native (as PC games)': 'Nativa (como jogos de PC)',
    'How the mouse turns the camera. Native turns it directly, as PC games do.':
        'Como o mouse gira a câmera. Nativa gira direto, como nos jogos de PC.',
    'Mouse sensitivity': 'Sensibilidade do mouse',
    'How far the camera turns for a mouse movement.': 'Quanto a câmera gira para cada movimento do mouse.',
    'Invert mouse vertical': 'Inverter mouse vertical',
    'Swaps up and down for the mouse.': 'Troca cima e baixo no mouse.',
    'Disable camera centering': 'Desativar centralização da câmera',
    'The camera no longer turns toward where you walk by itself. Suits the native mouse camera.':
        'A câmera deixa de virar sozinha para onde você anda. Combina com a câmera nativa do mouse.',
    'Invert camera X': 'Inverter câmera X',
    'Inverts left/right on the right stick.': 'Inverte esquerda/direita no analógico direito.',
    'Invert camera Y': 'Inverter câmera Y',
    'Inverts up/down on the right stick.': 'Inverte cima/baixo no analógico direito.',
    'Stick dead zone': 'Zona morta do analógico',
    'Default (24%)': 'Padrão (24%)',
    'How far a stick moves before the game sees it. Higher for a stick that drifts.':
        'Quanto o analógico precisa se mexer antes de o jogo perceber. Mais alto para um analógico com drift.',
    'Rumble strength': 'Força da vibração',
    'How strongly the controller rumbles.': 'A força com que o controle vibra.',
    'Motion controls (gyro)': 'Controles de movimento (giroscópio)',
    "Aim with the controller's gyroscope (bow, slingshot), as on the Switch. With Switch Pro, DualShock 4 and DualSense.":
        'Mire com o giroscópio do controle (arco, estilingue), como no Switch. Com Switch Pro, DualShock 4 e DualSense.',
    'Button prompts': 'Ícones de botões',
    'Which button icons the game shows in its texts and menus.': 'Quais ícones de botões o jogo mostra nos textos e menus.',
    'Volume': 'Volume',
    'How loud the game plays.': 'O volume do jogo.',
    'Mute in background': 'Mudo em segundo plano',
    'No sound while another window has the focus.': 'Sem som enquanto outra janela está em foco.',
    'Mesh shaders': 'Mesh shaders',
    'Native': 'Nativo',
    'Compute': 'Compute',
    'How grass, trees and foliage are drawn. Automatic picks what suits the GPU (AMD RX 6000: Compute, against driver crashes); Compute helps with driver problems.':
        'Como a grama, as árvores e a folhagem são desenhadas. Automático escolhe o que combina com a GPU (AMD RX 6000: Compute, contra crashes do driver); Compute ajuda com problemas de driver.',
    'Robust buffers': 'Buffers robustos',
    'Bounds-checked buffer reads: a bad read is dropped instead of stopping the GPU.':
        'Leituras de buffer com checagem de limites: uma leitura inválida é descartada em vez de travar a GPU.',
    'Descriptor reuse': 'Reúso de descritores',
    'Less work each frame while the game streams textures.': 'Menos trabalho a cada quadro enquanto o jogo carrega texturas.',
    'Sampler cache': 'Cache de samplers',
    'Faster sampler lookups while the game streams textures.': 'Buscas de sampler mais rápidas enquanto o jogo carrega texturas.',

    # the launcher's low-end rows (launcher.py LOW_END_ROWS)
    'Streaming and memory': 'Streaming e memória',
    'Legacy behavior': 'Comportamento antigo',
    'Balanced (recommended)': 'Equilibrado (recomendado)',
    'Lower memory': 'Menos memória',
    'Balanced sizes the Auto texture cache to system RAM and spreads cleanup of completed GPU resources across frames. Lower memory keeps smaller caches and reserves less video memory at startup; revisiting areas may require more loading. Texture quality stays the same. An explicit texture-memory limit is respected. Restart the game.':
        'Equilibrado ajusta o cache Auto de texturas à RAM e distribui a limpeza dos recursos de GPU usados entre os quadros. Menos memória usa caches menores e reserva menos memória de vídeo ao abrir; voltar a uma área pode carregar mais. A qualidade das texturas não muda. Um limite de memória de texturas definido é respeitado. Reinicie o jogo.',
    'RAM guard': 'Proteção de RAM',
    'Emergency (512 MB reserve)': 'Emergência (reserva de 512 MB)',
    'Standard (1 GB reserve)': 'Padrão (reserva de 1 GB)',
    'Strong (3 GB reserve)': 'Forte (reserva de 3 GB)',
    'When RAM or Windows commit runs short, the game releases unused textures. Emergency keeps minimum protection active; Off disables this RAM-reserve control. Normal texture and VRAM limits remain. Strong: for 16 GB RAM or many open programs.':
        'Quando a RAM ou a memória do Windows está acabando, o jogo libera texturas sem uso. Emergência mantém uma proteção mínima; Desligado desativa esse controle de reserva de RAM. Os limites normais de texturas e VRAM continuam. Forte: para 16 GB de RAM ou muitos programas abertos.',
    'Largest textures': 'Texturas grandes',
    'Standard (2048)': 'Padrão (2048)',
    '1024 (less VRAM)': '1024 (menos VRAM)',
    'Off (no dimension limit)': 'Desligado (sem limite de tamanho)',
    'Very large textures (64 MB and up) load at most this wide. 1024 saves video memory on 4-6 GB cards; those textures look a little softer. Off removes the dimension limit; memory limits still apply. Restart the game.':
        'Texturas muito grandes (64 MB ou mais) carregam com no máximo essa largura. 1024 economiza memória de vídeo em placas de 4-6 GB; essas texturas ficam um pouco mais suaves. Desligado tira o limite de tamanho; os limites de memória continuam valendo. Reinicie o jogo.',
    'Low-spec mode': 'Modo PC fraco',
    'low': 'baixo',
    'No extra helper threads for memory copies: eases CPUs with 4 cores or fewer. On strong CPUs rather slower. Restart the game.':
        'Sem threads extras para cópias de memória: alivia CPUs com 4 núcleos ou menos. Em CPUs fortes, tende a ser mais lento. Reinicie o jogo.',
    'Compact video memory (test)': 'Memória de vídeo compacta (teste)',
    'Keeps textures in a compacted area of their own, leaving the card more room. Can reduce stutter on tight cards. Experimental. Restart the game.':
        'Guarda as texturas numa área compacta só delas, deixando mais espaço na placa. Pode reduzir engasgos em placas com pouca memória. Experimental. Reinicie o jogo.',
    'Auto resolution: FPS target': 'Resolução automática: meta de FPS',
    '60 FPS (weak PC, down to 33%)': '60 FPS (PC fraco, até 33%)',
    'Lowers the render resolution step by step (down to 50%, or 33% on the weak-PC choice) when the graphics card misses the target, and raises it again when there is room, up to the Render resolution setting. Checks every 5 seconds so it does not jump around. Only helps when the graphics card is the bottleneck. Restart the game.':
        'Baixa a resolução interna aos poucos (até 50%, ou 33% na opção PC fraco) quando a placa de vídeo não alcança a meta, e sobe de novo quando sobra espaço, até o valor de Resolução interna. Confere a cada 5 segundos para não ficar pulando. Só ajuda quando a placa de vídeo é o gargalo. Reinicie o jogo.',
    'Fast pipelines (GPL, test)': 'Pipelines rápidos (GPL, teste)',
    'New scenes are drawn at once with a quickly linked pipeline while the full one is built in the background. Helps when characters show up as a flat silhouette or not at all the first time. Experimental: can stall briefly on some drivers. Restart the game.':
        'Cenas novas são desenhadas na hora com um pipeline montado rapidamente, enquanto o completo é criado em segundo plano. Ajuda quando personagens aparecem como uma silhueta chapada ou nem aparecem na primeira vez. Experimental: pode travar por um instante em alguns drivers. Reinicie o jogo.',

    # the launcher (launcher.py)
    'Ctrl+F8 in game marks a problem. F1 → Bug report also adds a marker.\n\nStutters and extended periods without new frames are recorded automatically. Afterwards, close the game and create a Debug Package. Please describe the room, boss or ocarina song and the steps that triggered the problem.\n\nThe optional Windows trace lasts 30 seconds and may add overhead. It also contains other programs’ activity and file paths. It is saved separately and is not automatically included in the Debug Package.':
        'Ctrl+F8 no jogo marca um problema. F1 → Jogo → Relatório de bug também adiciona uma marcação.\n\nEngasgos e períodos longos sem quadros novos são registrados automaticamente. Depois, feche o jogo e crie um Pacote de debug. Descreva a sala, o chefe ou a música da ocarina e os passos que causaram o problema.\n\nO trace opcional do Windows dura 30 segundos e pode pesar um pouco. Ele também contém a atividade de outros programas e caminhos de arquivos. Ele é salvo à parte e não entra automaticamente no Pacote de debug.',
    'Suggested changes for the next start:': 'Mudanças sugeridas para a próxima abertura:',
    'Apply these changes?': 'Aplicar essas mudanças?',
    'What changed in this version.': 'O que mudou nesta versão.',
    'Downloading …': 'Baixando …',
    'Navi on': 'Navi ligada',
    'Navi off': 'Navi desligada',
    'Music off': 'Música desligada',
    'Music on': 'Música ligada',
    'I understand this is an unstable alpha.': 'Entendo que esta é uma versão alfa instável.',
    'Not listed?': 'Não está na lista?',
    'Cheat tools (F1 → Debug)': 'Ferramentas de cheat (F1 → Debug)',
    'Turns on the tools in the game menu: no-clip flight, a free camera, mark and return, teleport, switch age, the inventory editor, the clock and movement speed.':
        'Ativa as ferramentas no menu do jogo: voo sem colisão, câmera livre, marcar posição e voltar, teleporte, trocar de idade, editor de inventário, relógio e velocidade de movimento.',
    'Protect hearts': 'Proteção de corações',
    'Link loses no hearts (hits still knock him back). Only with the cheat tools on.':
        'O Link não perde corações (os golpes ainda o empurram para trás). Só com as ferramentas de cheat ligadas.',
    'Monster health': 'Vida dos monstros',
    'How much life normal enemies have.': 'Quanta vida os inimigos normais têm.',
    'Boss health': 'Vida dos chefes',
    'How much life the bosses have.': 'Quanta vida os chefes têm.',
    'Damage from enemies': 'Dano dos inimigos',
    'How much damage Link takes from enemies and bosses.': 'Quanto dano o Link leva de inimigos e chefes.',
    'One-hit mode (hardcore)': 'Modo um golpe (hardcore)',
    'Every hit empties all hearts. Applies at the next start.': 'Cada golpe esvazia todos os corações. Vale a partir da próxima abertura.',
    'Diagnostics': 'Diagnóstico',
    'Problem details (optional)': 'Detalhes do problema (opcional)',
    'What happened? Room/boss/song, steps and approximate time. You can leave this blank.':
        'O que aconteceu? Sala/chefe/música, passos e horário aproximado. Pode deixar em branco.',
    "Don't show again": 'Não mostrar de novo',
    'Got it': 'Entendi',
    'There is no .nup file in it.': 'Não tem nenhum arquivo .nup aí dentro.',
    'Nothing measured yet: play a while, then this shows what holds it back and what helps.':
        'Nada medido ainda: jogue um pouco e aqui vai aparecer o que está segurando o desempenho e o que ajuda.',
    "From your last session (the game's own measurements):": 'Da sua última sessão (medições do próprio jogo):',
    'Preset applied. Applies at the next start.': 'Perfil aplicado. Vale a partir da próxima abertura.',
    "Downloading NVIDIA's DLSS SDK from NVIDIA's GitHub …": 'Baixando o DLSS SDK da NVIDIA do GitHub da NVIDIA …',
    'The new setup is downloaded from GitHub and checked, then it starts.': 'O novo instalador é baixado do GitHub e verificado, depois ele abre.',
    'Play': 'Jogar',
    'Please read before you start.': 'Leia antes de começar.',
    'This is a highly unstable development build. Crashes, freezes, graphical issues and broken gameplay are expected. It is provided only for testing.':
        'Este é um build de desenvolvimento bem instável. Crashes, travamentos, problemas gráficos e jogabilidade quebrada são esperados. Ele é disponibilizado só para testes.',
    'Continue': 'Continuar',
    'Activate Alpha Access': 'Ativar acesso alfa',
    'YOUR PC-ID': 'SEU PC-ID',
    'Copy PC-ID': 'Copiar PC-ID',
    'Load license file': 'Carregar arquivo de licença',
    'Select your license file': 'Escolha seu arquivo de licença',
    'The launcher reads your own NUP file, builds the game from it on this PC and then starts it. The NUP file is never changed or uploaded.':
        'O launcher lê o seu próprio arquivo NUP, cria o jogo a partir dele neste PC e depois abre o jogo. O arquivo NUP nunca é alterado nem enviado para lugar nenhum.',
    'NUP FILE ON THIS PC': 'ARQUIVO NUP NESTE PC',
    'Browse…': 'Procurar…',
    'or drop the NUP folder here.': 'ou arraste a pasta do NUP para cá.',
    'Install the game to': 'Instalar o jogo em',
    'Change': 'Alterar',
    'Game language': 'Idioma do jogo',
    'Automatic': 'Automático',
    'Disk space': 'Espaço em disco',
    'Select your Ocarina of Time game file': 'Escolha o seu arquivo do jogo Ocarina of Time',
    'Choose the game folder': 'Escolha a pasta do jogo',
    'Please select your .nup file first.': 'Escolha primeiro o seu arquivo .nup.',
    'No .nup file found. Select it with "Browse…" or drop it here.': 'Nenhum arquivo .nup encontrado. Escolha com "Procurar…" ou arraste para cá.',
    'Incomplete build found.': 'Build incompleto encontrado.',
    'The last build did not finish.': 'O último build não terminou.',
    'Resume': 'Continuar',
    'Restart': 'Recomeçar',
    'Discard': 'Descartar',
    'Starts it again with the same settings; the build reuses finished parts where that is safe.':
        'Começa de novo com as mesmas configurações; o build reaproveita as partes prontas quando é seguro.',
    'Throws the intermediate files away and builds from the start.': 'Joga fora os arquivos intermediários e faz o build do zero.',
    'Back to choosing the game file.': 'Volta para a escolha do arquivo do jogo.',
    'Update available': 'Atualização disponível',
    'A new version of Ocarina Reborn is installed. The game is rebuilt from the game data it already has; the .nup is not needed.':
        'Uma nova versão do Ocarina Reborn foi instalada. O jogo é recriado a partir dos dados que ele já tem; o .nup não é necessário.',
    'What happens': 'O que acontece',
    'Only what changed is compiled again. The first start then prepares the shaders. Your game folder and your settings stay as they are.':
        'Só o que mudou é compilado de novo. Depois, a primeira abertura prepara os shaders. A pasta do jogo e as suas configurações ficam como estão.',
    'Later': 'Depois',
    'Ocarina Reborn is ready.': 'O Ocarina Reborn está pronto.',
    'The first start prepares shaders. Time depends on your CPU and graphics driver.':
        'A primeira abertura prepara os shaders. O tempo depende da sua CPU e do driver de vídeo.',
    'GAME START': 'INÍCIO DO JOGO',
    'GAME': 'JOGO',
    'DIAGNOSTICS': 'DIAGNÓSTICO',
    'The game is running. Restoring and importing work once it is closed.':
        'O jogo está aberto. Restaurar e importar funcionam depois que ele for fechado.',
    'Making the backup …': 'Fazendo o backup …',
    'Restoring …': 'Restaurando …',
    'Importing …': 'Importando …',
    'Looking …': 'Procurando …',
    'Save data': 'Saves',
    'Backups of your save data, restoring and importing. Your current save is backed up automatically before every restore and import.':
        'Backups dos seus saves, restauração e importação. Antes de cada restauração e importação é feito um backup automático do seu save atual.',
    'RomFS mods in the emulator layout (a folder with "romfs"). Turn them on and off, add from a folder or a ZIP. Applies at the next start. exefs patches are not applied.':
        'Mods de RomFS no formato dos emuladores (uma pasta com "romfs"). Ligue e desligue, adicione de uma pasta ou de um ZIP. Vale a partir da próxima abertura. Patches de exefs não são aplicados.',
    'Classic UI · Classic HUD and controller icons': 'Interface clássica · HUD clássico e ícones de controle',
    'Choose Classic UI': 'Interface clássica',
    'Selection changed. Choose "Install and enable" to apply.': 'Seleção alterada. Escolha "Instalar e ativar" para aplicar.',
    'Preparing download …': 'Preparando o download …',
    'Classic HUD by kuledawg · Version 2.0.0': 'Classic HUD por kuledawg · Versão 2.0.0',
    'Enabled': 'Ativado',
    'Downloads only your selection: about 80 MB. On/off works offline afterwards. Other HUD mods may conflict.':
        'Baixa só o que você escolheu: cerca de 80 MB. Depois, ligar/desligar funciona offline. Outros mods de HUD podem dar conflito.',
    'Select your own voice ZIP': 'Escolha o seu ZIP de vozes',
    'Classic voices': 'Vozes clássicas',
    'Preparing your selected voice file. The first time can take about a minute …':
        'Preparando o arquivo de vozes escolhido. Na primeira vez pode levar cerca de um minuto …',
    'Reset ALL settings? Graphics, audio, controls, difficulty, cheats, colours and launcher preferences will return to defaults. Classic voices will be disabled.\n\nSaves, installed files and shader caches stay. Your current settings will be backed up.':
        'Redefinir TODAS as configurações? Gráficos, áudio, controles, dificuldade, cheats, cores e preferências do launcher voltam ao padrão. As vozes clássicas serão desativadas.\n\nSaves, arquivos instalados e caches de shaders ficam. É feito um backup das suas configurações atuais.',
    'All settings reset.': 'Todas as configurações foram redefinidas.',
    'Not saved yet': 'Ainda não salvo',
    'LOW PERFORMANCE COST': 'BAIXO CUSTO DE DESEMPENHO',
    'MEDIUM PERFORMANCE COST': 'CUSTO MÉDIO DE DESEMPENHO',
    'HIGH PERFORMANCE COST': 'ALTO CUSTO DE DESEMPENHO',
    'Settings': 'Configurações',
    'Set up NVIDIA DLSS': 'Configurar NVIDIA DLSS',
    'Reset all settings': 'Redefinir todas as configurações',
    'Reset graphics': 'Redefinir gráficos',
    'Save': 'Salvar',
    'Set up the game first.': 'Configure o jogo primeiro.',
    'Reborn Auto measures what holds your PC back and suggests settings that fit.\n\n1. Play 2-5 minutes somewhere you can repeat (e.g. Kokiri village → forest), then quit the game.\n2. You see the suggestion and decide.\n3. Play the same route again: Reborn Auto compares both runs.\n\nPlease keep frame generation off. No fps promise: only what really happens is measured.\n\nStart now?':
        'O Reborn Auto mede o que está segurando o seu PC e sugere configurações que combinam.\n\n1. Jogue 2-5 minutos num lugar que dê para repetir (por exemplo, Floresta Kokiri → Bosque Perdido) e feche o jogo.\n2. Você vê a sugestão e decide.\n3. Jogue o mesmo trajeto de novo: o Reborn Auto compara as duas rodadas.\n\nDeixe a geração de quadros desligada. Sem promessa de FPS: só o que acontece de verdade é medido.\n\nComeçar agora?',
    'No result.': 'Sem resultado.',
    'Prepare shaders and recorded pipelines now? Existing caches are reused. Time depends on your CPU and graphics driver. New effects may still stutter briefly on first use.':
        'Preparar os shaders e os pipelines gravados agora? Os caches existentes são reaproveitados. O tempo depende da sua CPU e do driver de vídeo. Efeitos novos ainda podem engasgar por um instante na primeira vez.',
    'Preparing shaders …': 'Preparando shaders …',
    'Windows trace (30 s)': 'Trace do Windows (30 s)',
    'Saved. Compare the same scenes on your next run. Previous settings are in the Reports folder.':
        'Salvo. Compare as mesmas cenas na próxima rodada. As configurações anteriores estão na pasta Reports.',
    'Still looking at your PC, try again in a moment.': 'Ainda analisando o seu PC, tente de novo daqui a pouco.',
    'Previous': 'Anterior',
    'Next': 'Próxima',
    '\n\nDownload and install it now? The launcher closes for it.': '\n\nBaixar e instalar agora? O launcher fecha para isso.',
    'Checking …': 'Verificando …',
    'Rebuild the game': 'Recriar o jogo',
    'Set up the game': 'Configurar o jogo',
    'Ready to build': 'Pronto para o build',
    'The game is built from your NUP file on this PC.': 'O jogo é criado a partir do seu arquivo NUP neste PC.',
    'Overall': 'No total',
    'The first start then prepares the shaders.': 'Depois, a primeira abertura prepara os shaders.',
    'Update': 'Atualizar',
    'Install': 'Instalar',
    'Supported': 'Suportado',
    'Not supported': 'Não suportado',
    'Not enough disk space.': 'Espaço em disco insuficiente.',
    'Choose the backup folder': 'Escolha a pasta de backup',
    'Your save data': 'Seus saves',
    'It stays as it is during the update. Making a backup first is still safer.':
        'Eles ficam como estão durante a atualização. Mesmo assim, fazer um backup antes é mais seguro.',
    'Backup location': 'Local do backup',
    'Change location': 'Alterar local',
    'Back up and update': 'Fazer backup e atualizar',
    'Update without backup': 'Atualizar sem backup',
    'Performance: tips': 'Desempenho: dicas',
    'Last session': 'Última sessão',
    'Game language (text)': 'Idioma do jogo (texto)',
    'Audio output': 'Saída de áudio',
    'Launcher language': 'Idioma do launcher',
    'Windows default': 'Padrão do Windows',
    'Backups, restore, import': 'Backups, restaurar, importar',
    'On/off, add from a ZIP or folder': 'Ligar/desligar, adicionar de um ZIP ou pasta',
    'Graphics, controls, audio, difficulty, cheats': 'Gráficos, controles, áudio, dificuldade, cheats',
    'Prepare shaders': 'Preparar shaders',
    'Less stutter, e.g. after a driver update': 'Menos engasgos, por exemplo depois de atualizar o driver',
    'Rebuild game': 'Recriar o jogo',
    'From your NUP file, again': 'A partir do seu arquivo NUP, de novo',
    'Open logs': 'Abrir logs',
    'Diagnostic tools': 'Ferramentas de diagnóstico',
    'Create debug package': 'Criar Pacote de debug',
    'Create Debug Package': 'Criar Pacote de debug',
    'Debug package created:': 'Pacote de debug criado:',
    'Measure, suggest, compare': 'Medir, sugerir, comparar',
    'There is no save data to back up yet.': 'Ainda não há saves para fazer backup.',
    'Pick a backup from the list first.': 'Escolha primeiro um backup da lista.',
    'No save data of this game found in the usual emulator folders. Use "Folder".':
        'Nenhum save deste jogo foi encontrado nas pastas comuns de emuladores. Use "Pasta".',
    'Choose the save folder': 'Escolha a pasta dos saves',
    'Choose a save file or ZIP': 'Escolha um arquivo de save ou ZIP',
    'There is no save data yet.': 'Ainda não há saves.',
    'Backup location: ': 'Local do backup: ',
    'When': 'Quando',
    'Kind': 'Tipo',
    'Reason': 'Motivo',
    'Files': 'Arquivos',
    'Size': 'Tamanho',
    'No backups yet.': 'Nenhum backup ainda.',
    'Create backup': 'Criar backup',
    'Restore': 'Restaurar',
    'Import: auto detect': 'Importar: detectar automaticamente',
    'Import: folder': 'Importar: pasta',
    'Import: file/ZIP': 'Importar: arquivo/ZIP',
    'Backup made and verified: ': 'Backup feito e verificado: ',
    'Restored. Your previous save is backed up as ': 'Restaurado. O backup do seu save anterior está em ',
    'Not restored, your save is unchanged: ': 'Não restaurado, seu save não mudou: ',
    'Not imported, your save is unchanged: ': 'Não importado, seu save não mudou: ',
    'Save folder': 'Pasta dos saves',
    'Backup folder': 'Pasta de backup',
    'Save or ZIP': 'Save ou ZIP',
    '. Applies at the next start of the game.': '. Vale a partir da próxima abertura do jogo.',
    'Applies at the next start of the game.': 'Vale a partir da próxima abertura do jogo.',
    'Applies at the next game start.': 'Vale a partir da próxima abertura do jogo.',
    'No mods yet. "Add mod" or open the folder.': 'Nenhum mod ainda. Use "Adicionar mod" ou abra a pasta.',
    'exefs only: no effect': 'só exefs: sem efeito',
    'Add mod (ZIP)': 'Adicionar mod (ZIP)',
    'Add mod (folder)': 'Adicionar mod (pasta)',
    'Open mods folder': 'Abrir pasta de mods',
    'Choose the mod folder': 'Escolha a pasta do mod',
    'Added: ': 'Adicionado: ',
    'off': 'desligado',
    'Turn off': 'Desligar',
    'Turn on': 'Ligar',
    'Please close the game first.': 'Feche o jogo primeiro.',
    'Not installed': 'Não instalado',
    'Controller icons': 'Ícones de controle',
    'HUD style': 'Estilo do HUD',
    'Title screen logo': 'Logo da tela de título',
    'Install and enable': 'Instalar e ativar',
    'Preparation failed.': 'A preparação falhou.',
    'Classic voice ready. Save to enable.': 'Voz clássica pronta. Salve para ativar.',
    'Please select the classic voice again to prepare it.': 'Escolha a voz clássica de novo para prepará-la.',
    'Classic UI enabled. Start the game to see the change.': 'Interface clássica ativada. Abra o jogo para ver a mudança.',
    'Difficulty': 'Dificuldade',
    'Saved. Applies at the next start.': 'Salvo. Vale a partir da próxima abertura.',
    "Reset every graphics setting to the game's defaults?\nControls, audio, saves and difficulty stay as they are.":
        'Redefinir todas as configurações gráficas para o padrão do jogo?\nControles, áudio, saves e dificuldade ficam como estão.',
    'Interface color': 'Cor da interface',
    'Interface color saved': 'Cor da interface salva',
    'Your color for the launcher and F1 menu. Changes are saved immediately.':
        'Sua cor para o launcher e o menu F1. As mudanças são salvas na hora.',
    'In game: F1 → Gameplay → Interface color.\nThe launcher picks up your in-game color when you return.':
        'No jogo: F1 → Jogo → Interface color.\nO launcher pega a cor escolhida no jogo quando você voltar.',
    'Choose color': 'Escolher cor',
    'Enter HEX': 'Digitar HEX',
    'Default color': 'Cor padrão',
    'Tunic color': 'Cor da túnica',
    'Hex color, e.g. #5080FF:': 'Cor em hex, por exemplo #5080FF:',
    'Hex color, e.g. #2E7BFF:': 'Cor em hex, por exemplo #2E7BFF:',
    'Enter six hex digits, e.g. #5080FF.': 'Digite seis dígitos hex, por exemplo #5080FF.',
    'For young Link and adult tunics. Also under F1 → Gameplay.\nSave and restart the game. The preview shows the selected color without lighting.':
        'Para as túnicas do Link criança e adulto. Também em F1 → Jogo.\nSalve e reinicie o jogo. A prévia mostra a cor escolhida sem iluminação.',
    'Amiibo removed.': 'amiibo removido.',
    'Ready for the next in-game amiibo scan.': 'Pronto para o próximo escaneamento de amiibo no jogo.',
    'Choose a figure for the next amiibo scan. No restart needed.': 'Escolha uma figura para o próximo escaneamento de amiibo. Não precisa reiniciar.',
    'Your amiibo file': 'Seu arquivo de amiibo',
    'Select your amiibo file': 'Escolha seu arquivo de amiibo',
    'No amiibo selected': 'Nenhum amiibo escolhido',
    'Choose .bin': 'Escolher .bin',
    'Remove': 'Remover',
    "1. Choose your own amiibo file (532, 540 or 572 bytes).\n2. Enable the game's amiibo feature and start a scan.\nChange files in game: F1 → Gameplay → Load amiibo (.bin).\nSelection applies immediately. Normal reward limits still apply.\nRead-only: no saving data to tags. Amiibo files are not included.":
        '1. Escolha o seu próprio arquivo de amiibo (532, 540 ou 572 bytes).\n2. Ative a função de amiibo do jogo e comece um escaneamento.\nTrocar de arquivo no jogo: F1 → Jogo → Load amiibo (.bin).\nA escolha vale na hora. Os limites normais de recompensa continuam valendo.\nSó leitura: nada é gravado nas tags. Arquivos de amiibo não estão incluídos.',
    'Your original file stays unchanged. If a scan is in progress, restart it after switching figures.':
        'O seu arquivo original não é alterado. Se houver um escaneamento em andamento, recomece depois de trocar de figura.',
    'Choose settings category': 'Escolha a categoria de configurações',
    'Presets:': 'Perfis:',
    'Applies at the next start. F1 → Debug → Enemy damage starts at this value and can change it in game.':
        'Vale a partir da próxima abertura. F1 → Debug → Enemy damage começa neste valor e pode ser alterado no jogo.',
    'Import your own voice ZIP, save and restart the game. No recordings are included.':
        'Importe o seu próprio ZIP de vozes, salve e reinicie o jogo. Nenhuma gravação está incluída.',
    'Import your own voice ZIP for attacks, damage and movement, then save; dedicated cutscene voices stay unchanged.':
        'Importe o seu próprio ZIP de vozes para ataques, dano e movimento e salve; as vozes próprias das cutscenes não mudam.',
    'Young Link: voice': 'Link criança: voz',
    'Adult Link: voice': 'Link adulto: voz',
    'Default': 'Padrão',
    'Classic (N64)': 'Clássica (N64)',
    'Point at a setting to see what it does.': 'Passe o mouse sobre uma configuração para ver o que ela faz.',
    'Saved automatically · No restart needed': 'Salvo automaticamente · Não precisa reiniciar',
    'The same settings as the in-game menu (F1). They apply at the next start of the game.':
        'As mesmas configurações do menu do jogo (F1). Elas valem a partir da próxima abertura do jogo.',
    'Low-end PC': 'PC fraco',
    'The new settings are in. Now play the same route as in the first run, at least 2 minutes, then quit the game. Then you see whether it got better.\n\nStart now?':
        'As novas configurações estão aplicadas. Agora jogue o mesmo trajeto da primeira rodada, pelo menos 2 minutos, e feche o jogo. Aí você vê se melhorou.\n\nComeçar agora?',
    'Cancel Reborn Auto and restore the previous settings?': 'Cancelar o Reborn Auto e restaurar as configurações anteriores?',
    'Memory was short for a while: RAM guard to Strong.': 'Faltou memória por um tempo: Proteção de RAM em Forte.',
    'Nothing clear to improve: your settings fit what was measured.': 'Nada claro para melhorar: suas configurações combinam com o que foi medido.',
    'Suggestion:': 'Sugestão:',
    'Apply and check with a second run?': 'Aplicar e conferir com uma segunda rodada?',
    'It got better. The new settings stay.': 'Melhorou. As novas configurações ficam.',
    'No measurable difference.': 'Nenhuma diferença mensurável.',
    'It got worse.': 'Piorou.',
    'Restore the previous settings?': 'Restaurar as configurações anteriores?',
    '  ·  second run pending': '  ·  falta a segunda rodada',
    'Record 30 seconds of system activity? The file can contain program names and file paths. After starting, switch to the running game within 5 seconds and reproduce the problem.':
        'Gravar 30 segundos de atividade do sistema? O arquivo pode conter nomes de programas e caminhos de arquivos. Depois de iniciar, volte para o jogo em até 5 segundos e reproduza o problema.',
    'Send this file to the developer.': 'Envie este arquivo para o desenvolvedor.',
    'Open shader dumps': 'Abrir dumps de shaders',
    'DLSS could not be downloaded:\n': 'Não foi possível baixar o DLSS:\n',
    'The update could not be downloaded:\n': 'Não foi possível baixar a atualização:\n',
    'The backup failed, the update was cancelled:\n': 'O backup falhou, a atualização foi cancelada:\n',
    'Enemy health could not be adjusted; the game starts as it is.': 'Não foi possível ajustar a vida dos inimigos; o jogo abre como está.',
    'Shaders prepared.': 'Shaders preparados.',
    'Checking': 'Verificando',
    'Needed': 'Necessário',
    'Free': 'Livre',
    'Recommended': 'Recomendado',
    'Selected model: ': 'Modelo escolhido: ',

    # the launcher's texts in English only (no German of their own)
    'Game files': 'Arquivos do jogo',
    'Help improve Ocarina Reborn': 'Ajude a melhorar o Ocarina Reborn',
    'Stutters or crashes? Your reports help us improve the game.': 'Engasgos ou crashes? Seus relatos ajudam a melhorar o jogo.',
    '1. MARK THE PROBLEM': '1. MARQUE O PROBLEMA',
    'If you notice stutters or crashes, press Ctrl+F8 when the problem happens, then close the game and create a fresh Debug Package.':
        'Se notar engasgos ou crashes, aperte Ctrl+F8 na hora em que o problema acontecer, depois feche o jogo e crie um Pacote de debug novo.',
    '2. SHARE YOUR REPORT': '2. ENVIE SEU RELATO',
    'Send it in #post-your-logs-here, in the Discord together with the area and what happened. Reports from lower-end PCs are especially helpful.':
        'Mande no #post-your-logs-here, no Discord, junto com a área e o que aconteceu. Relatos de PCs mais fracos ajudam especialmente.',
    'Could not save this preference. Please try again.\n\n': 'Não foi possível salvar esta preferência. Tente de novo.\n\n',
    'Private Alpha Build': 'Build alfa privado',
    'PRIVATE ALPHA BUILD': 'BUILD ALFA PRIVADO',
    'Build Workers': 'Workers do build',
    'Classic UI': 'Interface clássica',
    'Ocarina Reborn license': 'Licença do Ocarina Reborn',
    'Voice ZIP': 'ZIP de vozes',
    'Windows trace': 'Trace do Windows',
    'Debug Package': 'Pacote de debug',

    # dates, the update button, backups, colour presets, Classic UI choices
    'today': 'hoje',
    'yesterday': 'ontem',
    'Before-Update': 'Antes da atualização',
    'Before-Import': 'Antes da importação',
    'before-update': 'antes da atualização',
    'before-build': 'antes do build',
    'before-import': 'antes da importação',
    'before-restore': 'antes de restaurar',
    'Reborn Blue': 'Azul Reborn',
    'Ocean': 'Oceano',
    'Forest': 'Floresta',
    'Violet': 'Violeta',
    'Rose': 'Rosa',
    'Amber': 'Âmbar',
    'Silver': 'Prata',
    'Xbox (A/B swap)': 'Xbox (A/B trocados)',
    'PlayStation (X/O swap)': 'PlayStation (X/O trocados)',
    'Classic': 'Clássico',
    'Gold European': 'Dourado europeu',
    'Classic Black': 'Preto clássico',
    'Default (square)': 'Padrão (quadrado)',
    'Classic Yellow': 'Amarelo clássico',
    'Classic Blue': 'Azul clássico',

    # the Windows trace (trace_capture.py) and the update download
    'Windows Performance Recorder is only available on Windows.': 'O Windows Performance Recorder só existe no Windows.',
    'Windows Performance Recorder is not installed.': 'O Windows Performance Recorder não está instalado.',
    'For this optional Windows trace, close and run the launcher as administrator. Normal diagnostics do not require this.':
        'Para este trace opcional do Windows, feche e abra o launcher como administrador. O diagnóstico normal não precisa disso.',
    'Saving Windows trace…': 'Salvando o trace do Windows…',
    'OSError: the checksum does not match the release': 'O arquivo baixado não confere com a release (soma de verificação diferente).',

    # error messages of the launcher's helpers (amiibo.py, classic_ui.py, classic_voices.py, license.py, mods_manager.py,
    # save_manager.py, interface_theme.py, tunic_colors.py), shown through tr(str(error))
    'Expected a raw amiibo .bin file (532, 540 or 572 bytes).': 'Era esperado um arquivo .bin de amiibo bruto (532, 540 ou 572 bytes).',
    'The file could not be recognized as a raw amiibo tag. Check that it is an amiibo .bin dump.':
        'O arquivo não foi reconhecido como uma tag de amiibo bruta. Confira se é um dump .bin de amiibo.',
    'Prepare the game first, then select an amiibo.': 'Prepare o jogo primeiro e depois escolha um amiibo.',
    'Download cancelled. The installed HUD has not been changed.': 'Download cancelado. O HUD instalado não foi alterado.',
    'Invalid path in the mod archive.': 'Caminho inválido no arquivo do mod.',
    'Choose a controller style.': 'Escolha um estilo de controle.',
    'The selected HUD variant is missing or has an unexpected size.': 'A variante de HUD escolhida está faltando ou tem um tamanho inesperado.',
    'The Mods folder must not be a link for managed installation.': 'A pasta Mods não pode ser um link para a instalação gerenciada.',
    'Both enabled and disabled Classic UI folders exist. Check the Mods folder first.':
        'Existem pastas da Interface clássica ativada e desativada ao mesmo tempo. Confira a pasta Mods primeiro.',
    'The managed Classic UI folder must not be a link.': 'A pasta gerenciada da Interface clássica não pode ser um link.',
    'This launcher integration currently requires Windows.': 'Por enquanto, esta integração do launcher precisa do Windows.',
    'Close the game or any other operation using this game folder, then try again.':
        'Feche o jogo ou qualquer outra operação que esteja usando esta pasta do jogo e tente de novo.',
    'Build the game first. Its expected UI files were not found.': 'Faça o build do jogo primeiro. Os arquivos de interface esperados não foram encontrados.',
    'The download redirected outside GameBanana. Please use the mod page.': 'O download foi redirecionado para fora do GameBanana. Use a página do mod.',
    'Invalid archive range.': 'Intervalo inválido no arquivo compactado.',
    'GameBanana did not return the requested file part. Please retry later.': 'O GameBanana não devolveu a parte do arquivo pedida. Tente de novo mais tarde.',
    'Incomplete download. Please retry.': 'Download incompleto. Tente de novo.',
    'The mod archive has changed. This launcher needs an updated mod definition.':
        'O arquivo do mod mudou. Este launcher precisa de uma definição de mod atualizada.',
    'Unexpected mod archive.': 'Arquivo de mod inesperado.',
    'Invalid ZIP file header.': 'Cabeçalho de arquivo ZIP inválido.',
    'Choose a logo and HUD style.': 'Escolha um logo e um estilo de HUD.',
    'The Classic UI folder has no valid launcher manifest. Existing files were left untouched.':
        'A pasta da Interface clássica não tem um manifesto válido do launcher. Os arquivos existentes não foram alterados.',
    'Close the game before changing Classic UI.': 'Feche o jogo antes de mudar a Interface clássica.',
    'Install a Classic UI variant first.': 'Instale uma variante da Interface clássica primeiro.',
    'Some Classic UI files are missing. Choose "Install and enable" to repair them.':
        'Faltam alguns arquivos da Interface clássica. Escolha "Instalar e ativar" para repará-los.',
    'This controller variant needs game data version 1.1.1. Its resource-size table was not found.':
        'Esta variante de controle precisa dos dados do jogo na versão 1.1.1. A tabela de tamanhos de recursos não foi encontrada.',
    'Duplicate path in the mod archive.': 'Caminho duplicado no arquivo do mod.',
    'Unsupported mod archive format.': 'Formato de arquivo de mod não suportado.',
    'Unexpected file in this HUD variant.': 'Arquivo inesperado nesta variante de HUD.',
    'Archive member does not match its directory.': 'Um item do arquivo compactado não confere com o índice dele.',
    'Incomplete ZIP header.': 'Cabeçalho ZIP incompleto.',
    'Downloaded file checksum does not match. Please retry.': 'A soma de verificação do arquivo baixado não confere. Tente de novo.',
    'Installed file verification failed. The previous HUD is unchanged.': 'A verificação dos arquivos instalados falhou. O HUD anterior não foi alterado.',
    'Invalid BARS bank.': 'Banco BARS inválido.',
    'Unsupported BARS version.': 'Versão de BARS não suportada.',
    'Invalid BARS table.': 'Tabela BARS inválida.',
    'Unsupported interleaved BARS layout.': 'Layout BARS intercalado não suportado.',
    'No supported gameplay voices in this bank.': 'Nenhuma voz de jogo suportada neste banco.',
    "The imported voices exceed this bank's allocation. Original files were not changed.":
        'As vozes importadas passam do espaço deste banco. Os arquivos originais não foram alterados.',
    'Select Classic (N64) for Young Link first to prepare the voice.': 'Escolha Clássica (N64) para o Link criança primeiro, para preparar a voz.',
    'Select Classic (N64) for Adult Link first to prepare the voice.': 'Escolha Clássica (N64) para o Link adulto primeiro, para preparar a voz.',
    'Game audio changed. Select Default, then Classic (N64) again for Young Link.':
        'O áudio do jogo mudou. Escolha Padrão e depois Clássica (N64) de novo para o Link criança.',
    'Game audio changed. Select Default, then Classic (N64) again for Adult Link.':
        'O áudio do jogo mudou. Escolha Padrão e depois Clássica (N64) de novo para o Link adulto.',
    'Select your own voice ZIP. Voice recordings are not included or downloaded.':
        'Escolha o seu próprio ZIP de vozes. Gravações de voz não estão incluídas nem são baixadas.',
    'Voice ZIP is too large (maximum 64 MB / 512 files).': 'O ZIP de vozes é grande demais (máximo 64 MB / 512 arquivos).',
    'Unsupported AMTA metadata.': 'Metadados AMTA não suportados.',
    'Invalid AMTA name offset.': 'Posição de nome AMTA inválida.',
    'BARS name hash mismatch.': 'O hash de nome do BARS não confere.',
    'Invalid BWAV offset.': 'Posição BWAV inválida.',
    'Expected six hexadecimal digits': 'Digite seis dígitos hexadecimais',
    'no stable machine identifier is available': 'nenhum identificador fixo deste PC está disponível',
    'The license signature is invalid.': 'A assinatura da licença é inválida.',
    'The license has an unknown version.': 'A licença tem uma versão desconhecida.',
    'This license belongs to another PC.': 'Esta licença pertence a outro PC.',
    'This license is for another Ocarina Reborn build.': 'Esta licença é de outro build do Ocarina Reborn.',
    'The alpha license has expired.': 'A licença alfa expirou.',
    'The license file is damaged.': 'O arquivo de licença está corrompido.',
    'no mod in it (a mod is a folder that holds a romfs folder)': 'nenhum mod aqui (um mod é uma pasta que contém uma pasta romfs)',
    'a folder or a .zip file': 'uma pasta ou um arquivo .zip',
    'the backup is incomplete or was changed': 'o backup está incompleto ou foi alterado',
    'the game is running: close it first': 'o jogo está aberto: feche-o primeiro',
    'No save data of this game found there (looked for account.sav and slot_00/progress.sav).':
        'Nenhum save deste jogo foi encontrado aí (foram procurados account.sav e slot_00/progress.sav).',
    "Unsupported emulator save state. Please select the game's actual save-data folder.":
        'Save state de emulador não suportado. Escolha a pasta de saves de verdade do jogo.',
    'This file is not Ocarina Reborn save data. Select the save folder (it holds account.sav and slot_00 ...).':
        'Este arquivo não é um save do Ocarina Reborn. Escolha a pasta dos saves (ela contém account.sav e slot_00 ...).',
    "This looks like a save of the Nintendo 64 game (or one of its PC ports). That is another game with another save format; it cannot be converted to this game's saves.":
        'Isso parece um save do jogo de Nintendo 64 (ou de um dos ports dele para PC). É outro jogo, com outro formato de save; não dá para converter para os saves deste jogo.',
    'Use six hexadecimal digits, for example #5080FF.': 'Use seis dígitos hexadecimais, por exemplo #5080FF.',
}

_PATTERNS = [(re.compile('(.*?)'.join(map(re.escape, key.split('{}'))), re.S), pt) for key, pt in FORMATS.items()]


def tr(en):
    """the launcher's English text (or a list of texts) in its language: pt-BR from here, else as it is"""
    if UI_LANG[0] != 'pt-BR':
        return en
    if isinstance(en, (list, tuple)):
        return type(en)(tr(x) for x in en)
    if not isinstance(en, str):
        return en
    if en in TEXT:
        return TEXT[en]
    for pattern, pt in _PATTERNS:
        m = pattern.fullmatch(en)
        if m:
            return pt.format(*m.groups())
    return en
