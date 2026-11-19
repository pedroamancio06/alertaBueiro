# Roteiro do vídeo: AlertaBueiro (até 5:00)

Meta: 4:40 de fala, deixando 20 s de folga para cortes. Ritmo calmo, cerca de 140 palavras por minuto.
Cada bloco tem o que aparece na tela e a fala para ler. Os números são todos reais, medidos no protótipo.

## Antes de gravar

1. Abrir https://alertabueiro-api.onrender.com/health e esperar `"ok": true` (o servidor grátis hiberna).
2. Abrir o painel e deixar na aba *Mapa e fila*, com o zoom inicial.
3. Separar 2 fotos no computador: uma boca de lobo **entupida** (para o relato) e uma **limpa** (para a foto do depois).
   Teste as duas antes no painel: a entupida precisa sair como `total` e a limpa como `limpa`.
4. Abrir `model/confusion_matrix.png` numa aba para mostrar no bloco 5.
5. Fechar notificações, aumentar o zoom do navegador para 110% e gravar em 1080p.

## Bloco 1: Problema (0:00 a 0:40)

**Tela:** foto ou vídeo de rua alagada; depois, os números em texto grande.

> Toda vez que chove forte em São Paulo, o CGE registra de 15 a 22 pontos de alagamento, muitos deles na zona sul.
> Uma das causas, segundo a própria Prefeitura, é boca de lobo entupida com lixo e entulho.
> Só em um ano foram 8.900 reclamações de bueiro sujo no SP156.
> O problema é que a limpeza é reativa. O chamado entra na fila por ordem de chegada,
> e ninguém sabe qual boca de lobo limpar primeiro quando vem um temporal.

## Bloco 2: Solução e público (0:40 a 1:15)

**Tela:** mockup do WhatsApp (foto enviada e resposta "Recebido! Risco 78/100") e, em seguida, o painel.

> O AlertaBueiro transforma a foto do morador em uma fila de limpeza priorizada por risco de alagamento.
> O morador manda a foto pelo WhatsApp, sem cadastro. A inteligência artificial confere se a boca de lobo
> está entupida, junta relatos repetidos do mesmo ponto e calcula uma nota de risco de 0 a 100.
> A subprefeitura recebe essa fila pronta e manda a equipe antes da chuva, não depois da enchente.
> O piloto é na Subprefeitura Cidade Ademar, na zona sul.

## Bloco 3: Arquitetura e as 4 tecnologias (1:15 a 2:00)

**Tela:** diagrama do fluxo (o do README serve): foto, API, LGPD, YOLOv8, Neon, painel.
Destaque cada tecnologia quando ela for citada.

> A foto chega numa API hospedada na **nuvem**, no Render, com banco geoespacial no Neon.
> Antes de qualquer coisa, a API borra rostos e placas e guarda o telefone só como hash, como pede a LGPD.
> Depois entra a **visão computacional**: um YOLOv8 treinado por nós identifica a boca de lobo e diz se está livre ou obstruída.
> O banco agrupa relatos a menos de 30 metros num único ponto.
> A **inteligência artificial** de risco combina quatro fatores: gravidade da obstrução, chuva prevista para 24 horas,
> histórico de alagamento perto do ponto e vulnerabilidade da região.
> E a **análise de dados** aparece no painel: mapa de calor, fila e indicadores.

## Bloco 4: Demonstração (2:00 a 3:00)

**Tela:** gravação do painel, nesta ordem.

1. Aba *Enviar foto*: enviar a foto da boca de lobo entupida.

> Vou mandar uma foto como se fosse um morador.
> Em cerca de 2 segundos o modelo detecta a boca de lobo obstruída, calcula o score e mostra de onde veio cada ponto da nota.

2. Mostrar a tabela de fatores e a legenda com o tempo total.

> Cada nota é explicável: aqui está quanto a gravidade, a chuva, o histórico e a vulnerabilidade pesaram.

3. Aba *Alerta de chuva*: clicar em "Simular chuva forte (40 mm)".

> Agora simulo uma previsão de 40 milímetros. A fila se reorganiza sozinha
> e o sistema gera o alerta com os 10 pontos de maior risco. Os pontos do mapa são simulados para a demonstração.

4. Voltar ao mapa (pontos vermelhos), gerar a ordem de serviço do primeiro da fila.
5. Aba *Ordens de serviço*: enviar a foto da boca de lobo limpa.

> A equipe limpa e manda a foto do depois. O próprio modelo confirma a desobstrução, fecha o chamado e isso vira prova de serviço.

## Bloco 5: Resultados, validação e expansão (3:00 a 4:40)

**Tela:** `metrics.json` ou um slide com os números; depois a matriz de confusão; por fim, um slide com as 3 etapas e o modelo de negócio.

> Agora, os resultados. O modelo foi treinado com datasets públicos e avaliado em imagens que nunca viu.
> Ele chegou a mAP50 de 0,83. Para bocas de lobo limpas, 0,95. Para obstruídas, 0,70.
> O F1 ficou em 0,79, bem perto da nossa meta de 0,80.
> Na matriz de confusão, das 8 bocas de lobo entupidas do teste, o modelo acertou 7.
> Quando erra, ele tende a marcar uma limpa como entupida, ou seja, erra a favor da segurança:
> o custo é uma vistoria a mais, não um alagamento.
> O conjunto de teste ainda é pequeno, por isso o próximo passo é treinar com fotos reais da Cidade Ademar.

> Na nuvem, o processamento completo da foto, incluindo a anonimização, leva cerca de 2 segundos,
> dentro do requisito de 3 segundos.

> A validação tem três etapas. Primeiro, a prova técnica que vocês acabaram de ver.
> Depois, um piloto de 6 meses em 2 quilômetros quadrados da Cidade Ademar, comparado com uma área parecida sem o sistema.
> As metas são limpar 70% dos pontos de alto risco antes de cada chuva forte, em menos de 72 horas,
> e reduzir em 20% as ocorrências de alagamento. Por fim, a escala para as 32 subprefeituras e outras capitais.

> O modelo de negócio é gratuito para o cidadão e cobra licença SaaS da prefeitura ou da concessionária de limpeza,
> por subprefeitura monitorada, contratável por edital de inovação. E como o SP156 já atende por WhatsApp,
> o AlertaBueiro pode entrar como camada de priorização, sem concorrer com ele.

> O projeto contribui com os ODS 11, 13, 10 e 3: cidades mais resilientes ao clima, com prioridade para quem é mais vulnerável.
> AlertaBueiro: limpar antes da chuva, não depois da enchente.

## Cuidados com o que dizer

1. **Dados simulados:** os pontos do mapa e as ocorrências históricas são simulados. Diga isso uma vez (já está no bloco 4).
2. **Classes do modelo:** o modelo atual separa *limpa* e *obstruída*. Não diga que ele identifica o tipo de resíduo
   ou a obstrução parcial; isso fica como evolução.
3. **Metas do piloto** são metas, não resultados. Use "a meta é", nunca "reduzimos".
4. **Fotos locais:** o treino usou só datasets públicos. Fotos da Cidade Ademar são o próximo passo.

## Edição

1. Corte as pausas e os carregamentos do painel (a requisição de 2 s pode ficar, ela prova a velocidade).
2. Coloque legendas com os números principais: 15 a 22 pontos, 8.900 reclamações, mAP50 0,83, 7 de 8, 2 s.
3. Confira que as 4 palavras aparecem na tela pelo menos uma vez: visão computacional, IA, análise de dados, nuvem.
4. Duração final: até 5:00. Publicar no YouTube como **não listado** e enviar o .txt com o link na FIAP ON.
