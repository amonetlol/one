# one — backup dos desktops

Snapshot da máquina **one (CachyOS)**, coletado em **25/10/2026**. As configurações da máquina de origem não foram alteradas.

## Conteúdo

- Hyprland: padrão, Besita, Pie, Karol, Vora e Kana, incluindo Kitty, barras, launchers, notificações, binds e scripts próprios.
- Niri: Noctalia, DMS e Serpantinum, com configurações dos shells e runtime local do Serpantinum.
- Qtile/X11: configuração Python, ambiente, Polybar, Rofi e wallpaper.
- Compartilhados: Bash, Starship, terminais, aplicador/perfis GTK, temas, ícones, cursores, fontes, helpers e unidades systemd relacionadas.
- Entradas de sessão SDDM e wrappers em `/usr/local/bin`.
- Hyprexpo corrigido: binários instalados, patch e código-fonte utilizado no build.
- Imagens fixas encontradas nas referências das configurações.

Os arquivos em `payload/` são TAR.GZ. Preservam permissões e links simbólicos Linux, inclusive ao clonar o repositório no Windows. Arquivos maiores são divididos em partes de até 48 MiB; `restore.py` faz a junção automaticamente. O inventário completo está em `manifests/*-files.json`, e os checksums em `manifest.json`.

## Restaurar em outro Linux

Clone este repositório e execute com **Python 3.11 ou superior**:

```bash
python3 restore.py --verify
python3 restore.py --apply --system
```

`--verify` somente confere a integridade. `--apply` restaura os arquivos do usuário, adapta `/home/pio` ao home de destino e preserva colisões em `~/.local/state/one-restore-backup-DATA/`. Arquivos existentes fora do snapshot não são removidos.

`--system` também instala as entradas de sessão e os wrappers de sistema usando `sudo`; os arquivos de sistema anteriores ficam em `/var/backups/one-desktops-DATA/`. Para restaurar somente o usuário, use `python3 restore.py --apply`.

O código do hyprexpo é restaurado em `~/.local/share/one-backup-sources/hyprexpo`. Nenhum serviço, sessão ou atualização de pacotes é iniciado pelo restaurador.

## Antes do primeiro login

1. Instale os aplicativos/dependências necessários à sessão escolhida. `manifests/packages-versions.txt`, `packages-explicit.txt` e `packages-foreign.txt` registram os pacotes da origem, incluindo versões e pacotes externos aos repositórios oficiais. São inventários da máquina inteira, não uma lista mínima para instalação automática.
2. Ajuste os monitores nas configurações de cada perfil: a origem usa **VMware / Virtual-1 / 1920×1080**, com adaptações de renderização por software e XWayland. Essas opções podem precisar mudar no novo hardware.
3. Confira locale `pt_BR.UTF-8`, teclado ABNT2 e diretórios como `~/Imagens/wallpapers`.
4. O binário do hyprexpo exige o **Hyprland 0.56.2, commit `efb50993780079460b0cbed1363e2166a2de1d9f`**, e bibliotecas compatíveis. Para outra versão, recompile o fonte incluído contra os headers do Hyprland instalado antes de entrar na sessão. Não descarregue/recarregue o plugin em uma sessão em uso.
5. Confira `manifests/wallpaper-unresolved.txt` e `manifests/missing.txt`. Depois de instalar as unidades, execute `systemctl --user daemon-reload`; o restaurador não habilita timers/serviços automaticamente.

Para recompilar o hyprexpo, após instalar compilador, `make`, `pkg-config`, headers do Hyprland e dependências de desenvolvimento indicadas no Makefile:

```bash
cd ~/.local/share/one-backup-sources/hyprexpo
make CXX=clang++ hyprexpo.so
```

Copie o binário resultante para `plugins/hyprexpo.so` dos perfis desejados, com a sessão correspondente encerrada. Os seis perfis têm sua própria cópia.

## Limites do snapshot

- A biblioteca aleatória de wallpapers (aproximadamente 1,4 GB) não foi incluída. Sua lista está em `manifests/wallpaper-library.txt`; as imagens fixas referenciadas foram incluídas quando encontradas.
- Históricos de navegador, cookies, credenciais SSH, caches, logs, backups antigos e dados de sessão não fazem parte do backup.
- DMS e Noctalia instalados por pacote precisam ser instalados no destino. O runtime local do Serpantinum e o shell Karol personalizado foram incluídos.
- Os TAR.GZ mantêm o conteúdo da origem; a adaptação do home ocorre somente ao restaurar.
- Integridade e uma restauração isolada das configurações foram verificadas. As sessões gráficas não foram iniciadas em outro sistema.
