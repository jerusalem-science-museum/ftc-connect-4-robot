set clipboard=unnamedplus

" Basic settings
set nocompatible
set number
set relativenumber
set cursorline
set scrolloff=8
set signcolumn=yes

" Indentation
set tabstop=4
set shiftwidth=4
set expandtab
set smartindent
set autoindent

" Search
set ignorecase
set smartcase
set hlsearch
set incsearch

" Quality of life
set nowrap
set noswapfile
set nobackup
set undofile
set undodir=~/.vim/undodir
set clipboard=unnamedplus
set mouse=a
set updatetime=50
set timeoutlen=300
set backspace=indent,eol,start
set encoding=utf-8

" Colors
set termguicolors
set background=dark
syntax on
colorscheme desert        " built-in dark scheme, no plugins needed

" Netrw (built-in file browser)
let g:netrw_banner=0
let g:netrw_liststyle=3

" Leader
let mapleader = " "

" Basic mappings
nnoremap <leader>e :Explore<CR>
nnoremap <leader>w :w<CR>
nnoremap <leader>q :q<CR>
nnoremap <C-d> <C-d>zz
nnoremap <C-u> <C-u>zz
nnoremap n nzzzv
nnoremap N Nzzzv
vnoremap J :m '>+1<CR>gv=gv
vnoremap K :m '<-2<CR>gv=gv

" Clear search highlight
nnoremap <Esc> :nohlsearch<CR>

" Split navigation
nnoremap <C-h> <C-w>h
nnoremap <C-j> <C-w>j
nnoremap <C-k> <C-w>k
nnoremap <C-l> <C-w>l