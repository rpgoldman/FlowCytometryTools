#!/usr/bin/env python
# A script to read FCS 3.0 formatted file (and potentially FCS 2.0 and 3.1)
# Eugene Yurtsev 07/20/2013
# (I do not promise this works)
# Distributed under the MIT License
# TODO: Throw an error if there is logarithmic amplification (or else implement support for it)
import sys
import numpy
import warnings

try:
    import pandas
    pandas_found = True
except ImportError:
    print('You do not have pandas installed, so the parse_fcs function can only be used together with numpy.')
    pandas_found = False
except Exception as e:
    print('Your pandas is improperly configured. It raised the following error {0}'.format(e))
    pandas_found = False

def raise_parser_feature_not_implemented(message):
    print """ Some of the parser features have not yet been implemented.
              If you would like to see this feature implemented, please send a sample FCS file
              to the developers.
              The following problem was encountered with your FCS file:
              {0} """.format(message)

    raise Exception(message)


def parse_text(raw_text, fcs_version, flow_cytometer=None):
    """ """
    pass


class FCS_Parser(object):
    """
    A Parser for .fcs files.
    Should work for FCS 3.0
    May work for other FCS formats (2.0, 3.1)

    self.annotation['header'] holds the parsed HEADER segment
    self.annotation['text'] holds the parsed TEXT segment
    self.data holds the parsed DATA segment
    self.analysis holds the parsed ANALYSIS segment (Not yet implemented.)

    For convenience the names of the channels are available in:
    self.channel_names holds the names of the channels
    """
    #TODO Implement return ANALYSIS segment

    def __init__(self, path, read_data=True):
        self._data = None
        self.annotation = {}
        self.path = path

        with open(path,'rb') as f:
            self.read_header(f)
            self.read_text(f)
            if read_data:
                self.read_data(f)

    def read_header(self, file_handle):
        """
        Reads the header of the FCS file.
        The header specifies where the annotation, data and analysis are located inside the binary file.
        """
        header = {}
        header['FCS format'] = file_handle.read(6)

        if header['FCS format'] != 'FCS3.0':
            warnings.warn("""This parser was designed with the FCS 3.0 format in mind. It may or may not work for other FCS formats.""")

        file_handle.read(4) # 4 space characters after the FCS format

        for field in ['text start', 'text end', 'data start', 'data end', 'analysis start', 'analysis end']:
            header[field] = int(file_handle.read(8))

        if header['data start'] == 0 or header['data end'] == 0:
            raise_parser_feature_not_implemented("""The locations of data start and end are located in the TEXT section of the data. However,
            this parser cannot handle this case yet. Please send the sample fcs file to the developer. """)

        if header['analysis start'] != 0:
            warnings.warn('There appears to be some information in the ANALYSIS segment of file {0}. However, might be unable to read it correctly.'.format(self.path))

        self.annotation['header'] = header


    def read_text(self, file_handle):
        """
        Reads the TEXT segment of the FCS file.
        This is the meta data associated with the FCS file.
        Converting all meta keywords to lower case.
        """
        header = self.annotation['header'] # For convenience

        #####
        # Read in the TEXT segment of the FCS file
        file_handle.seek(header['text start'], 0)
        raw_text = file_handle.read(header['text end'] - header['text start'] + 1).strip()

        #####
        # Parse the TEXT segment of the FCS file into a python dictionary
        delimiter = raw_text[0] # Remove white spaces that may arise due to differences in FCS formats

        if raw_text[-1] != delimiter:
            raise_parser_feature_not_implemented('Parser expects the same delimiter character in beginning and end of TEXT segment')

        raw_text_segments = raw_text[1:-1].split(delimiter) # Using 1:-1 to remove first and last characters which should be reserved for delimiter
        keys, values = raw_text_segments[0::2], raw_text_segments[1::2]
        text = {key : value for key, value in zip(keys, values)} # Build dictionary

        ####
        # Extract channel names and convert some of the channel properties and other fields into numeric data types (from string)
        # Note: do not use regular expressions for manipulations here. Regular expressions are too heavy in terms of computation time.
        pars = int(text['$PAR'])
        if '$P0B' in keys: # Checking whether channel number count starts from 0 or from 1
            self.channel_numbers = range(0, pars) # Channel number count starts from 0
        else:
            self.channel_numbers = range(1, pars + 1) # Channel numbers start from 1

        self.channel_names = tuple([text['$P{0}N'.format(i)] for i in self.channel_numbers])

        # Convert some of the fields into integer values
        keys_encoding_bits  = ['$P{0}B'.format(i) for i in self.channel_numbers]
        keys_encoding_range = ['$P{0}R'.format(i) for i in self.channel_numbers]
        add_keys_to_convert_to_int = ['$NEXTDATA', '$PAR', '$TOT']

        keys_to_convert_to_int = keys_encoding_bits + add_keys_to_convert_to_int

        for key in keys_to_convert_to_int:
            value = text[key]
            text[key] = int(value)

        self.annotation['text'] = text

        ### Keep for debugging
        #key_list = self.header['text'].keys()
        #for key in sorted(text.keys()):
            #print key, text[key]
        #raise Exception('here')


    def check_assumptions(self):
        """
        Checks the FCS file to make sure that some of the assumptions made by the parser are met.
        """
        text = self.annotation['text']
        keys = text.keys()

        if '$NEXTDATA' in text and text['$NEXTDATA'] != 0:
            raise_parser_feature_not_implemented('Not implemented $NEXTDATA is not 0')

        if '$MODE' not in text or text['$MODE'] != 'L':
            raise_parser_feature_not_implemented('Mode not implemented')

        if '$P0B' in keys:
            raise_parser_feature_not_implemented('Not expecting a parameter starting at 0')

        if text['$BYTEORD'] not in ["1,2,3,4", "4,3,2,1", "1,2", "2,1"]:
            raise_parser_feature_not_implemented('$BYTEORD {} not implemented'.format(text['$BYTEORD']))

        # TODO: check logarithmic amplification


    def read_data(self, file_handle):
        """ Reads the DATA segment of the FCS file. """
        self.check_assumptions()
        header, text = self.annotation['header'], self.annotation['text'] # For convenience
        num_events = text['$TOT'] # Number of events recorded
        num_pars   = text['$PAR'] # Number of parameters recorded

        # TODO: Kill white space in $byteord
        if text['$BYTEORD'] == '1,2,3,4' or text['$BYTEORD'] == '1,2':
            endian = '<'
        elif text['$BYTEORD'] == '4,3,2,1' or text['$BYTEORD'] == '2,1':
            endian = '>'

        conversion_dict = {'F' : 'f4', 'D' : 'f8'} # matching FCS naming convention with numpy naming convention f4 - 4 byte (32 bit) single precision float

        if text['$DATATYPE'] not in conversion_dict.keys():
            raise_parser_feature_not_implemented('$DATATYPE = {0} is not yet supported.'.format(text['$DATATYPE']))

        dtype = '{endian}{numerical_type}'.format(endian=endian, numerical_type=conversion_dict[text['$DATATYPE']])

        # Calculations to figure out data types of each of parameters
        bytes_per_par_list   = [text['$P{0}B'.format(i)] / 8  for i in self.channel_numbers]
        par_numeric_type_list   = ['{endian}f{size}'.format(endian=endian, size=bytes_per_par) for bytes_per_par in bytes_per_par_list]
        bytes_per_event = sum(bytes_per_par_list)
        total_bytes = bytes_per_event * num_events

        # Parser for list mode. Here, the order is a list of tuples. where each tuples stores event related information
        file_handle.seek(header['data start'], 0) # Go to the part of the file where data starts

        # Read in the data
        if len(set(par_numeric_type_list)) > 1:
            data = numpy.fromfile(file_handle, dtype=','.join(par_numeric_type_list), count=num_events)
            raise_parser_feature_not_implemented('The different channels were saved using mixed numeric formats')
        else:
            data = numpy.fromfile(file_handle, dtype=dtype, count=num_events * num_pars)
            data = data.reshape((num_events, num_pars))

        self._data = data

    @property
    def data(self):
        """ Holds the parsed DATA segment of the FCS file. """
        if self._data is None:
            with open(self.path, 'rb') as f:
                self.read_data()
        return self._data


def parse_fcs(path, meta_data_only=False, output_format='DataFrame', compensate=False):
    """
    Parse an fcs file at the location specified by the path.

    Parameters
    ----------
    path : str
        Path of .fcs file
    meta_data_only : bool
        If True, the parse_fcs only returns the meta_data (the TEXT segment of the FCS file)
    output_format : 'DataFrame' | 'ndarray'
        If set to 'DataFrame' the returned

    Returns
    -------
    if meta_data_only is True:
        meta_data : dict
            Contains a dictionary with the meta data information
    if meta_data is False:
        a 3-tuple with
            the first element the meta_data (dictionary)
            the second element the data (in either DataFrame or numpy format)
            the third element a tuple containing the names of the channels (only for numpy output)

    Examples
    --------
    fname = '../tests/data/EY_2013-05-03_EID_214_PID_1120_Piperacillin_Well_B7.001.fcs'
    meta = parse_fcs(fname, meta_data_only=True)
    meta, data_pandas = parse_fcs(fname, meta_data_only=False, output_format='DataFrame')
    meta, data_numpy, channels  = parse_fcs(fname, meta_data_only=False, output_format='ndarray')
    """
    if compensate == True:
        raise_parser_feature_not_implemented('Compensation has not been implemented yet.')

    parsed_FCS = FCS_Parser(path)
    meta = parsed_FCS.annotation
    channel_names = parsed_FCS.channel_names

    if meta_data_only:
        return meta
    elif output_format == 'DataFrame':
        """ Constructs pandas DF object """
        if pandas_found == False:
            raise Exception('You do not have pandas installed.')
        data = parsed_FCS.data
        data = pandas.DataFrame(data, columns=parsed_FCS.channel_names)
        return meta, data
    elif output_format == 'ndarray':
        """ Constructs numpy matrix """
        return meta, parsed_FCS.data, channel_names
    else:
        raise Exception("The output_format must be either 'ndarray' or 'DataFrame'")



###################
### Test code #####
###################

def compare_against_fcm():
    from fcm import loadFCS as parse_fcs
    print 'Comparing fcm reader and EYs reader'
    import time
    tic = time.time()
    fname = './tests/sample_data/2.fcs'
    #fname = './tests/sample_data/Miltenyi.fcs'

    for i in range(1):
        x = FCS_Parser(fname).get_data()
        y = parse_fcs(fname, transform=None, auto_comp=False)


    #import FlyingButterfly
    #from FlyingButterfly.FlyingButterfly import set_pret
    print y[:22, 6] - x[:22, 6]
    #print x[:2, :]

    toc = time.time()
    print toc-tic
    #tic = time.time()
    #toc = time.time()

    #print toc-tic


if __name__ == '__main__':
    #fname = '../tests/data/AY_2013-06-08_gasperm_ecoli_Well_A1.001.fcs'
    #fname = '../tests/data/AY_2013-06-08_gasperm_ecoli_Well_A2.001.fcs'
    #fname = '../tests/data/AY_2013-06-08_gasperm_ecoli_Well_B1.001.fcs'
    #fname = '../tests/data/AY_2013-06-08_gasperm_ecoli_Well_B2.001.fcs'
    fname = '../tests/data/EY_2013-05-03_EID_214_PID_1120_Piperacillin_Well_B7.001.fcs'
    meta = parse_fcs(fname, meta_data_only=True)
    meta, data_pandas = parse_fcs(fname, meta_data_only=False, output_format='DataFrame')
    meta, data_numpy, channels  = parse_fcs(fname, meta_data_only=False, output_format='ndarray')
    print 'hello'



