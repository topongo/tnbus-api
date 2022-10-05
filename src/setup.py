import setuptools
from tnbus.version import version

setuptools.setup(
    name='tnbus',
    version=version,
    description="Interface with the Trentino Trasporti API for real-time bus tracking.",
    url='https://github.com/topongo/bodoConnect',
    author='Lorenzo Bodini',
    author_email='lorenzo.bodini.private@gmail.com',
    packages=['tnbus'],
    python_requires='>=3.6',
    license="GPL3",
    platform="posix"
)
