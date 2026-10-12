# TensorFold for SIP-0111's S, G0 and G1 on the Spark (#2199): the pinned recipe's runtime.
# NVIDIA's PyTorch container by digest (the RUNBOOK's DGX Spark base), then TensorFold at its v0.6.6
# release commit. TensorFold compiles its CUDA kernels on first use with the container's torch, nvcc
# and ninja; the build cache is mounted (TORCH_EXTENSIONS_DIR, TRITON_CACHE_DIR) so a restart reuses
# it. The frozen dependency list is written into the image and read into each run's record.
FROM nvcr.io/nvidia/pytorch:26.07-py3@sha256:2140e699b3beaf7f96a0081fd9c9406bc3832b435cdb60dfa2d261f7d2f34a1c

ARG TENSORFOLD_COMMIT=cb2ebf0540f42604e2759b2ddef497861e928248
RUN python -m pip install --no-cache-dir "git+https://github.com/ashhart/TensorFold.git@${TENSORFOLD_COMMIT}" \
 && python -m pip freeze > /opt/tensorfold-frozen.txt \
 && python -c "import tensorfold; print(tensorfold.__version__)" > /opt/tensorfold-version.txt

LABEL org.opencontainers.image.source="https://github.com/ashhart/TensorFold" \
      org.opencontainers.image.revision="${TENSORFOLD_COMMIT}"
ENTRYPOINT ["tensorfold"]
