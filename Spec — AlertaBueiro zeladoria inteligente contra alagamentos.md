# Spec — AlertaBueiro: zeladoria inteligente contra alagamentos

Nov 16, 2026 · @Pedro

## Visão geral

O AlertaBueiro transforma fotos enviadas por moradores em uma fila de limpeza priorizada por risco de alagamento. Assim, a subprefeitura limpa bocas de lobo **antes** da chuva forte, não depois da enchente.

- **Área da GS2:** 1 — Cidades Inteligentes, Mobilidade e Infraestrutura (com interface na área 8, IoT e alertas).
- **Entregável:** vídeo-pitch técnico de até 5 min, prazo 19/11/2026.
- **Tecnologias obrigatórias:** visão computacional, análise de dados, cloud e IA, todas no fluxo principal.
- **Recorte do piloto:** zona sul de São Paulo (Subprefeitura Cidade Ademar).

## Problema e evidências

Bocas de lobo entupidas agravam alagamentos, e a limpeza hoje é reativa: depende de reclamação avulsa no SP156, sem critério de risco.

- **Causa conhecida:** a própria Prefeitura afirma que resíduos e entulho em bocas de lobo, ramais e galerias contribuem para os alagamentos ([Subprefeitura Aricanduva](https://prefeitura.sp.gov.br/web/aricanduva/w/zeladoria_urbana/67862)).
- **Volume de reclamações:** a falta de limpeza de bueiros gerou 8.900 notificações no SP156 em cerca de um ano, a 2ª maior causa de reclamação sobre limpeza urbana ([Gazeta SP](https://www.gazetasp.com.br/estado/lixo-em-bueiros-foi-2a-maior-reclamacao-contra-empresas-de-limpeza-em/)).
- **Frequência:** temporais isolados já geram de 15 a 22 pontos de alagamento na capital segundo o CGE, incluindo a zona sul ([SBT News](https://sbtnews.sbt.com.br/noticia/brasil/chuva-forte-atinge-a-grande-sp-e-defesa-civil-envia-alerta-severo-para-alagamentos), [IstoÉ Dinheiro](https://istoedinheiro.com.br/defesa-civil-alerta-para-chuva-forte-com-risco-de-granizo-e-ventos-em-sp-ate-terca-feira)).
- **Lacuna:** o SP156 registra o chamado, mas não diz qual boca de lobo limpar primeiro quando vem chuva forte.

**Ligação com CitizenTech:** quem mais perde com alagamento são moradores de periferia, em fundos de vale e perto de córregos. O cidadão vira sensor, e a tecnologia transforma o relato em ação preventiva.

## Público-alvo e stakeholders

O beneficiário direto é o morador de área sujeita a alagamento; o cliente pagante é o poder público ou a concessionária de limpeza.

| Ator | Papel | O que ganha |
| --- | --- | --- |
| Morador de área de risco | Envia fotos pelo WhatsApp ou app | Menos alagamento na rua, retorno sobre o chamado |
| Subprefeitura / zeladoria | Usa o painel e a fila priorizada | Equipes onde o risco é maior, antes da chuva |
| Empresa de limpeza contratada | Recebe ordens de serviço com foto e local | Rotas otimizadas, prova de serviço com foto do depois |
| Defesa Civil / CGE | Consome alertas e mapa de calor | Visão de pontos críticos antes do temporal |
| Associações de bairro e ONGs | Mobilizam moradores | Voz organizada da comunidade |

**Mercado:** começa em São Paulo (32 subprefeituras) e escala para outras capitais com alagamento recorrente. A adoção pelo cidadão é barata porque usa o WhatsApp, que ele já tem.

## Solução e fluxo do usuário

Uma foto do cidadão vira, em segundos, um ponto no mapa com nota de risco; a fila se reordena sozinha quando a previsão indica chuva forte.

1. **Relato:** o morador manda foto e localização pelo WhatsApp (ou PWA). Não precisa de cadastro.
2. **Detecção:** o modelo de visão computacional identifica a boca de lobo e classifica a obstrução: limpa, parcial ou total; lixo, entulho, folhas ou sedimento.
3. **Deduplicação:** relatos a menos de 30 m do mesmo ponto são agrupados; mais relatos aumentam a confiança.
4. **Score de risco:** a IA combina gravidade, previsão de chuva, histórico de alagamento e vulnerabilidade da área em uma nota de 0 a 100.
5. **Fila priorizada:** o painel da subprefeitura mostra os pontos ordenados e gera ordens de serviço com rota.
6. **Limpeza e prova:** a equipe fotografa o depois; o modelo confirma a desobstrução e fecha o chamado.
7. **Retorno:** o morador recebe pelo WhatsApp a foto do serviço feito.

Na véspera de chuva forte, o sistema dispara um **alerta preventivo** para a zeladoria com os 10 pontos de maior risco.

## Requisitos

O MVP precisa cobrir RF01 a RF06; o restante entra no roadmap.

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF01 | Receber foto + geolocalização via WhatsApp ou PWA | MVP |
| RF02 | Detectar boca de lobo e classificar obstrução (3 níveis) e tipo de resíduo | MVP |
| RF03 | Agrupar relatos duplicados por raio de 30 m | MVP |
| RF04 | Calcular score de risco 0–100 por ponto | MVP |
| RF05 | Painel com mapa de calor e fila priorizada | MVP |
| RF06 | Validar limpeza pela foto do depois | MVP |
| RF07 | Alerta preventivo quando a previsão passar de 30 mm/24 h | Roadmap |
| RF08 | Notificar o morador do andamento | Roadmap |
| RF09 | Rotas otimizadas para as equipes | Roadmap |

| ID | Requisito não funcional |
| --- | --- |
| RNF01 | Inferência da imagem em menos de 3 s |
| RNF02 | Funcionar com foto de celular de entrada e 3G |
| RNF03 | LGPD: rostos e placas borrados automaticamente; telefone guardado com hash |
| RNF04 | Acessibilidade: fluxo por WhatsApp com áudio e texto simples |
| RNF05 | Explicabilidade: cada score mostra os fatores que o compuseram |

## Arquitetura e tecnologias obrigatórias

Toda foto percorre o mesmo caminho na nuvem: ingestão, visão computacional, banco geoespacial, IA de risco e painel.

&#91;embedded content: arquitetura · da foto à ordem de serviço\]

A equipe de limpeza fecha o ciclo: a ordem de serviço sai do painel, e a foto do depois volta pela mesma API para validação.

| Tecnologia exigida | Onde atua na solução | Implementação sugerida |
| --- | --- | --- |
| Visão computacional | Detecta a boca de lobo, mede a obstrução e valida a foto do depois | YOLOv8 (Ultralytics) com fine-tuning em dataset do Roboflow + fotos locais |
| Inteligência artificial | Score de risco e anonimização de rostos e placas | Regra ponderada no MVP, XGBoost no piloto |
| Análise de dados | Mapa de calor, fila, indicadores do piloto | Pandas + GeoPandas; painel em Streamlit ou Power BI |
| Cloud | Hospeda API, modelo, banco e fotos | Cloud Run ou AWS Lambda; PostgreSQL + PostGIS gerenciado; armazenamento de objetos |

## Modelo de dados e IA de risco

O score de risco começa como uma soma ponderada explicável e, com dados do piloto, passa a ser um modelo de gradient boosting treinado contra as ocorrências reais do CGE.

**Score v1 (regra explicável, usada no protótipo):**

```latex
Risco = 100 \cdot (0{,}35\,G + 0{,}30\,C + 0{,}20\,H + 0{,}15\,V)
```

G = gravidade da obstrução pela visão computacional; C = chuva prevista nas próximas 24 h, normalizada; H = histórico de alagamento a até 300 m; V = vulnerabilidade (densidade e renda do setor censitário). Todos de 0 a 1.

**Score v2 (roadmap):** XGBoost com rótulo "houve alagamento a até 300 m em 48 h", validado por área sob a curva (AUC).

**Fontes de dados**

| Fonte | Uso |
| --- | --- |
| Fotos dos moradores | Gravidade e tipo de resíduo |
| Previsão de chuva (API Open-Meteo ou INMET) | Fator C |
| Ocorrências de alagamento do CGE | Fator H e rótulos do v2 |
| Setores censitários do IBGE | Fator V |
| GeoSampa (drenagem, córregos, relevo) | Contexto geográfico |

**Entidades principais:** Relato (foto, lat/long, data, telefone com hash), Ponto (boca de lobo agrupada, score, status), Ordem de serviço (ponto, equipe, foto antes/depois, tempos), Alerta (data, chuva prevista, pontos).

## Diferencial

As alternativas atuais registram ou varrem por calendário; o AlertaBueiro decide **onde limpar primeiro** com base no risco real.

| Critério | SP156 (portal, app, WhatsApp) | Limpeza por cronograma | AlertaBueiro |
| --- | --- | --- | --- |
| Como nasce a demanda | Chamado de texto | Calendário fixo | Foto analisada por IA |
| Priorização | Ordem de chegada | Nenhuma | Score de risco + previsão de chuva |
| Duplicados | Um chamado por pessoa | Não se aplica | Agrupados por ponto |
| Prova de serviço | Status manual | Relatório da empresa | Foto do depois validada pelo modelo |
| Momento da ação | Depois da reclamação | Independe do risco | Antes do temporal |

O SP156 já tem atendimento por WhatsApp com IA ([Olhar Digital](https://olhardigital.com.br/2023/10/18/pro/sp-atendimento-pelo-156-agora-pode-ser-feito-pelo-whatsapp/)). Por isso, o AlertaBueiro pode se integrar a ele como camada de priorização, em vez de concorrer.

## Resultados, validação e expansão

Este bloco vale 8 dos 20 pontos do vídeo. A meta do piloto é limpar 70% dos pontos de alto risco antes de cada chuva forte. As metas abaixo são hipóteses a validar, não resultados medidos.

| Indicador | Como medir | Meta do piloto (6 meses) |
| --- | --- | --- |
| Pontos de alto risco limpos antes da chuva | OS fechadas antes da data do alerta | ≥ 70% |
| Tempo médio entre relato e limpeza (alto risco) | Data do relato vs. foto do depois | < 72 h |
| Ocorrências de alagamento na área | CGE: piloto vs. mesmo período do ano anterior e vs. área controle | Queda de 20% |
| Precisão do modelo de visão | F1 em conjunto de teste rotulado | ≥ 0,80 |
| Relatos duplicados no SP156 | Chamados de bueiro na área | Queda de 30% |
| Engajamento | Moradores ativos por mês | 500 |

**Validação em 3 etapas**

1. **Prova técnica (agora):** modelo treinado em dataset público + 50 fotos reais da Cidade Ademar; métricas de precisão e recall.
2. **Piloto (6 meses):** uma subprefeitura, cerca de 2 km² com histórico de alagamento, comparada a uma área controle semelhante.
3. **Escala:** zona sul inteira, depois as 32 subprefeituras e outras capitais.

**Modelo de negócio:** gratuito para o cidadão. Receita com licença SaaS para prefeituras e concessionárias de limpeza, cobrada por subprefeitura ou por km² monitorado, contratável via edital de inovação (Marco Legal das Startups, CPSI). Receita secundária: relatórios de risco para seguradoras e condomínios.

**Sustentabilidade:** custo de nuvem baixo (inferência serverless) e o canal WhatsApp elimina o custo de aquisição de usuários.

## ODS, privacidade e plano de entrega

**ODS relacionadas**

| ODS | Meta | Contribuição |
| --- | --- | --- |
| 11 — Cidades e Comunidades Sustentáveis | 11.5 (reduzir perdas por desastres, incluindo os relacionados à água) | Menos alagamentos por drenagem obstruída |
| 13 — Ação Contra a Mudança Global do Clima | 13.1 (resiliência a riscos climáticos) | Zeladoria guiada pela previsão de chuva |
| 9 — Indústria, Inovação e Infraestrutura | 9.1 (infraestrutura resiliente) | Manutenção preventiva de drenagem |
| 10 — Redução das Desigualdades | 10.2 (inclusão) | Prioridade a áreas vulneráveis via fator V |
| 3 — Saúde e Bem-Estar | 3.9 (doenças por contaminação da água) | Menos exposição à água de enchente (leptospirose) |

**Privacidade e ética (LGPD):** dados mínimos e sem cadastro. Rostos e placas são borrados antes de armazenar, o telefone é guardado com hash e as fotos são apagadas 90 dias após o fechamento. O fator de vulnerabilidade só aumenta prioridade e nunca a reduz.

**Escopo do protótipo para o vídeo:** detector YOLOv8 treinado em dataset público do Roboflow (bueiros, lixo), uma API na nuvem, um painel com mapa de calor e a fila de risco usando dados simulados mais as ocorrências reais do CGE. O fluxo pelo WhatsApp pode ser mostrado como mockup.

**Plano de 3 dias** (o item C do TCC vence 17/11, então o primeiro dia é leve)

- [ ] 17/11 — Coletar 30 a 50 fotos de bocas de lobo no bairro; escolher o dataset no Roboflow
- [ ] 17/11 — Treinar o YOLOv8 no Google Colab e salvar as métricas (F1, mAP)
- [ ] 18/11 — Subir a API de inferência (FastAPI) em Cloud Run, Azure ou AWS Lambda
- [ ] 18/11 — Montar o painel em Streamlit ou Power BI: mapa de calor, fila e score
- [ ] 18/11 — Escrever o roteiro nos 5 blocos (bloco 5 com cerca de 2 min)
- [ ] 19/11 — Gravar a demo de tela e a narração; editar até 5 min
- [ ] 19/11 — Publicar no YouTube como não listado; enviar o .txt com o link na FIAP ON
