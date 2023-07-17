from setuptools import setup, find_packages

setup(
    name='c3',
    version='0.1.0',
    author='The CLAIMED authors',
    author_email='your@email.com',
    description='Description of your package',
    url='https://github.com/yourusername/your-package-name',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'c3 = c3.compiler:main'
        ]
    },
    package_data={
        'c3': ['./c3/generate_kfp_component.ipynb'],
    },
    install_requires=[
        'ipython',
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
