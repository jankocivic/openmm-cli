import click

@click.command()
@click.argument('name')
@click.option('--count', default=1, help='number of greetings')
def hello(count, name):
    for i in range(count):
        click.echo(f'Hello {name}!')

if __name__ == '__main__':
    hello()
