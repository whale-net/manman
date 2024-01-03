
if __name__ == '__main__':
    print('hello world, it is I, host')
    import black
    print('black imported')

    from manman.test_shared.sample import Sample
    print(Sample.value)

    print("hello modify", "how it work")