# XDP-L2-Guard Documentation

This directory contains the authoritative technical documentation for the XDP-L2-Guard project.

## Core Documentation
- **[Comprehensive Engineering Manual (LaTeX)](technical_guide.tex)** - The single source of truth for the project. This document combines high-level system architecture, low-level data plane implementation details, control plane orchestration, and operational diagnostics into one continuous guide. It is designed to be compiled into a professional PDF using standard LaTeX toolchains (e.g., `pdflatex`).

## Compilation Instructions
To generate the PDF from the `.tex` source:

```bash
# Using standard pdflatex (Ubuntu/Debian)
sudo apt-get install texlive-latex-extra texlive-fonts-recommended texlive-science
pdflatex technical_guide.tex
```
*Alternatively, you can upload the file to a cloud compiler like Overleaf.*

## Other Resources
- **[Project Root README](../README.md)** - High-level project overview and quickstart instructions.
