# Autogenerated file
def render(name, orders):
    yield """<!doctype html>
<html>
  <head>
    <title>Microdot + uTemplate example</title>
  </head>
  <body>
    <h1>List of Orders:</h1>
    """
    if name:
        yield """    <p>Customer Name: <b>"""
        yield str(name)
        yield """</b>!</p>
    """
    yield """    <ul>
    """
    for order in orders:
        yield """        <li>"""
        yield str(order)
        yield """</li>
    """
    yield """    </ul>
  </body>
</html>"""
