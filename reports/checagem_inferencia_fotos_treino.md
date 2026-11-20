# Verificação de integração do modelo com as quatro fotos do treinamento

Este relatório verifica somente que o modelo treinado é carregado e executa a inferência. **Não é avaliação independente**, pois as imagens foram usadas no treino.

| Foto | Score de peixe-leão (não calibrado) | Saída com limiares conservadores |
|---|---:|---|
| peixe_leao_01.jpeg | 0,9757 | Inconclusivo |
| peixe_leao_02.jpeg | 0,9848 | Inconclusivo |
| peixe_leao_03.jpeg | 0,9178 | Inconclusivo |
| peixe_leao_04.jpeg | 0,9841 | Inconclusivo |

Por segurança, o projeto exige score ≥0,995 para o rótulo "possível peixe-leão" no modelo experimental; com menos de 0,05 retorna "não identificado"; os demais são inconclusivos. Esses limiares não são calibrados, portanto não significam qualidade científica. O modelo não é adequado para identificar peixes em produção; toda ocorrência segue para validação humana.

Suíte automatizada: **569 testes aprovados** (`python -m pytest -q`) neste ambiente. Testes de câmera/GPS/navegador e avaliação com outros peixes reais não foram feitos.
