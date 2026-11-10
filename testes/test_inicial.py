from previsao_vendas import main


def test_main_exibe_mensagem(capsys):
    main()

    resultado = capsys.readouterr()

    assert resultado.out.strip() == "Hello from previsao-vendas!"
